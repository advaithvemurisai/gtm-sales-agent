import logging
import os
import time
from collections import deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv
load_dotenv()

from backend.config import MAX_COMPANY_NAME_LENGTH, MAX_PRODUCT_DESCRIPTION_LENGTH
from backend.errors import is_billing_error
from backend.agent.icp import infer_icp_signals
from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gtm_agent.api")
_request_windows: dict[str, deque] = {}
_RATE_LIMIT = 5
_RATE_WINDOW_SECONDS = 60

app = FastAPI(title="GTM Sales Intelligence Agent")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if origin.strip()
]

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


ShortText = Annotated[str, Field(max_length=80)]


class IcpProfile(BaseModel):
    """A seller-reviewed ICP; bounded so edited criteria can't bloat or hijack the verdict prompt."""
    model_config = ConfigDict(extra="forbid")

    target_company_size: ShortText | None = None
    funding_stage: list[ShortText] = Field(default_factory=list, max_length=8)
    tech_signals: list[ShortText] = Field(default_factory=list, max_length=10)
    hiring_signals: list[ShortText] = Field(default_factory=list, max_length=10)
    budget_indicator: ShortText | None = None


class AnalyzeRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=MAX_COMPANY_NAME_LENGTH)
    product_description: str = Field(min_length=1, max_length=MAX_PRODUCT_DESCRIPTION_LENGTH)
    company_website: str | None = Field(default=None, max_length=200)
    icp_profile: IcpProfile | None = None


class AnalyzeResponse(BaseModel):
    company_name: str
    icp_profile: dict
    verdict: dict
    evidence: dict
    summary: dict


@app.post("/analyze")
def analyze(request: AnalyzeRequest, http_request: Request) -> AnalyzeResponse:
    """
    Infer an ICP from the product description, gather web evidence about the
    company, and return a PURSUE / WATCH / DEPRIORITIZE verdict with its evidence.
    """
    started_at = time.perf_counter()
    # Behind a proxy this is the real client IP only when uvicorn runs with
    # --proxy-headers and --forwarded-allow-ips (see README).
    client_key = http_request.client.host if http_request.client else "unknown"
    if not _allow_request(client_key, time.monotonic()):
        raise HTTPException(status_code=429, detail="Too many analysis requests. Please try again shortly.")
    logger.info("Analyze request received for company=%s", request.company_name)
    try:
        # Reuse an edited profile when the seller has reviewed the inference.
        if request.icp_profile:
            icp_profile = request.icp_profile.model_dump()
        else:
            icp_profile = infer_icp_signals(request.product_description)
        icp_profile["raw_description"] = request.product_description

        # Run evaluation pipeline
        result = run_evaluation_pipeline(
            company_name=request.company_name,
            icp_profile=icp_profile,
            company_website=request.company_website,
        )

        # Format response
        verdict = format_verdict_display(result["verdict"])

        evidence = {
            "company_signals": result["web_search"]["raw_data"].get("company_signals", {}),
            "technology": result["technology"]["summary"],
            "hiring": result["hiring"]["summary"],
            "web_search": result["web_search"]["summary"],
            "source_errors": {
                source: result[source]["raw_data"].get("error")
                for source in ("technology", "hiring", "web_search")
                if result[source]["raw_data"].get("error")
            },
            "source_urls": {
                source: result[source]["raw_data"].get("source_urls", [])
                for source in ("technology", "hiring", "web_search")
            },
        }

        summary = {
            "decision": verdict["decision"],
            "signal_count": len(verdict.get("signals", [])),
            "reasoning_preview": verdict.get("reasoning", "")[:220],
            "evidence_sources": ["company_signals", "technology", "hiring", "web_search"],
            "confidence": verdict.get("confidence", "unknown"),
        }

        logger.info(
            "Analyze response prepared for company=%s with decision=%s duration_ms=%.1f",
            request.company_name,
            verdict["decision"],
            (time.perf_counter() - started_at) * 1000,
        )

        return AnalyzeResponse(
            company_name=request.company_name,
            icp_profile=icp_profile,
            verdict=verdict,
            evidence=evidence,
            summary=summary,
        )

    except Exception as e:
        logger.exception(
            "Analyze pipeline failed for company=%s duration_ms=%.1f",
            request.company_name,
            (time.perf_counter() - started_at) * 1000,
        )
        if is_billing_error(e):
            return JSONResponse(
                status_code=503,
                content={"detail": "Live research is paused right now.", "code": "demo_paused"},
            )
        raise HTTPException(status_code=500, detail="Analysis failed. Check the server logs for details.")


def _allow_request(client_key: str, now: float) -> bool:
    """Sliding-window rate limit per client; drops idle clients so memory stays bounded."""
    for key in [key for key, window in _request_windows.items() if not window or now - window[-1] > _RATE_WINDOW_SECONDS]:
        del _request_windows[key]
    window = _request_windows.setdefault(client_key, deque())
    while window and now - window[0] > _RATE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _RATE_LIMIT:
        return False
    window.append(now)
    return True


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
