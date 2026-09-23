import logging
import os
import time
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

from backend.config import MAX_COMPANY_NAME_LENGTH, MAX_PRODUCT_DESCRIPTION_LENGTH
from backend.agent.icp_conversation import infer_icp_signals
from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gtm_agent.api")
_request_windows = defaultdict(deque)
_RATE_LIMIT = 5
_RATE_WINDOW_SECONDS = 60

app = FastAPI(title="GTM Sales Intelligence Agent")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
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


class AnalyzeRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=MAX_COMPANY_NAME_LENGTH)
    product_description: str = Field(min_length=1, max_length=MAX_PRODUCT_DESCRIPTION_LENGTH)


class AnalyzeResponse(BaseModel):
    company_name: str
    verdict: dict
    evidence: dict
    summary: dict


@app.post("/analyze")
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run full evaluation pipeline: ICP conversation -> Phase 2 evaluation -> verdict.
    For MVP, we skip the interactive ICP conversation and go straight to evaluation
    with a default ICP profile.
    """
    started_at = time.perf_counter()
    client_key = "analyze"
    now = time.monotonic()
    window = _request_windows[client_key]
    while window and now - window[0] > _RATE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many analysis requests. Please try again shortly.")
    window.append(now)
    logger.info("Analyze request received for company=%s", request.company_name)
    try:
        # Infer all ICP fields from product description - nothing hardcoded
        icp_profile = infer_icp_signals(request.product_description)
        icp_profile["raw_description"] = request.product_description

        # Run evaluation pipeline
        result = run_evaluation_pipeline(
            company_name=request.company_name,
            icp_profile=icp_profile
        )

        # Format response
        verdict = format_verdict_display(result["verdict"])

        evidence = {
            "company_signals": result["web_search"]["raw_data"].get("company_signals", {}),
            "builtwith": result["builtwith"]["summary"],
            "careers": result["careers"]["summary"],
            "web_search": result["web_search"]["summary"],
            "source_errors": {
                source: result[source]["raw_data"].get("error")
                for source in ("builtwith", "careers", "web_search")
                if result[source]["raw_data"].get("error")
            },
            "source_urls": {
                source: result[source]["raw_data"].get("source_urls", [])
                for source in ("builtwith", "careers", "web_search")
            },
        }

        summary = {
            "decision": verdict["decision"],
            "signal_count": len(verdict.get("signals", [])),
            "reasoning_preview": verdict.get("reasoning", "")[:220],
            "evidence_sources": ["company_signals", "builtwith", "careers", "web_search"],
            "confidence": verdict.get("confidence", "medium"),
        }

        logger.info(
            "Analyze response prepared for company=%s with decision=%s duration_ms=%.1f",
            request.company_name,
            verdict["decision"],
            (time.perf_counter() - started_at) * 1000,
        )

        return AnalyzeResponse(
            company_name=request.company_name,
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
        raise HTTPException(status_code=500, detail="Analysis failed. Check the server logs for details.")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
