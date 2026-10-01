import json
import logging
import os
import queue
import re
import threading
import time
from collections import deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator
from dotenv import load_dotenv
load_dotenv()

from backend.config import MAX_COMPANY_NAME_LENGTH, MAX_PRODUCT_DESCRIPTION_LENGTH
from backend.errors import is_billing_error
from backend.agent.icp import infer_icp_signals
from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.response import build_analysis_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gtm_agent.api")
_request_windows: dict[str, deque] = {}
_RATE_LIMIT = 5
_RATE_WINDOW_SECONDS = 60
# Number of reverse proxies in front of the app that append to X-Forwarded-For (0 = none, use the socket IP).
_TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
_HOSTNAME = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)

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

    @field_validator("company_website")
    @classmethod
    def _valid_website(cls, value: str | None) -> str | None:
        """Accept a hostname or http(s) URL; the value is interpolated into search prompts."""
        value = (value or "").strip()
        if not value:
            return None
        host = re.sub(r"^https?://", "", value, flags=re.I).split("/")[0].split(":")[0]
        if not _HOSTNAME.match(host) or re.search(r"\s", value):
            raise ValueError("company_website must be a hostname or URL like example.com")
        return value


class AnalyzeResponse(BaseModel):
    company_name: str
    icp_profile: dict
    verdict: dict
    evidence: dict


class _AnalysisError(Exception):
    """A failed analysis, already mapped to an HTTP status and a client-safe message."""

    def __init__(self, status_code: int, detail: str, code: str | None = None):
        self.status_code, self.detail, self.code = status_code, detail, code


def _run_analysis(request: AnalyzeRequest, progress=lambda stage: None) -> dict:
    """Infer the ICP, run the pipeline, and shape the response. Raises _AnalysisError on failure."""
    started_at = time.perf_counter()
    logger.info("Analyze request received for company=%s", request.company_name)
    try:
        # Reuse an edited profile when the seller has reviewed the inference.
        if request.icp_profile:
            icp_profile = request.icp_profile.model_dump()
        else:
            progress("icp")
            icp_profile = infer_icp_signals(request.product_description)
        icp_profile["raw_description"] = request.product_description

        result = run_evaluation_pipeline(
            company_name=request.company_name,
            icp_profile=icp_profile,
            company_website=request.company_website,
            on_progress=progress,
        )
        response = build_analysis_response(request.company_name, icp_profile, result)

        logger.info(
            "Analyze response prepared for company=%s with decision=%s duration_ms=%.1f",
            request.company_name,
            response["verdict"]["decision"],
            (time.perf_counter() - started_at) * 1000,
        )
        return response

    except Exception as e:
        logger.exception(
            "Analyze pipeline failed for company=%s duration_ms=%.1f",
            request.company_name,
            (time.perf_counter() - started_at) * 1000,
        )
        if is_billing_error(e):
            raise _AnalysisError(503, "Live research is paused right now.", "demo_paused")
        raise _AnalysisError(500, "Analysis failed. Check the server logs for details.")


def _check_rate_limit(http_request: Request) -> None:
    if not _allow_request(_client_ip(http_request), time.monotonic()):
        raise HTTPException(status_code=429, detail="Too many analysis requests. Please try again shortly.")


@app.post("/analyze")
def analyze(request: AnalyzeRequest, http_request: Request) -> AnalyzeResponse:
    """
    Infer an ICP from the product description, gather web evidence about the
    company, and return a PURSUE / WATCH / DEPRIORITIZE verdict with its evidence.
    """
    _check_rate_limit(http_request)
    try:
        return AnalyzeResponse(**_run_analysis(request))
    except _AnalysisError as error:
        if error.code:
            return JSONResponse(status_code=error.status_code, content={"detail": error.detail, "code": error.code})
        raise HTTPException(status_code=error.status_code, detail=error.detail)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/analyze/stream")
def analyze_stream(request: AnalyzeRequest, http_request: Request):
    """Same analysis as /analyze, streamed as server-sent events: `stage` events as each real stage
    starts (icp, research, verdict), then one `result` or `error` event."""
    _check_rate_limit(http_request)
    events: queue.Queue = queue.Queue()

    def work():
        try:
            events.put(("result", AnalyzeResponse(**_run_analysis(request, lambda stage: events.put(("stage", {"stage": stage})))).model_dump()))
        except _AnalysisError as error:
            events.put(("error", {"detail": error.detail, "code": error.code or "server"}))
        events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _client_ip(http_request: Request) -> str:
    """The socket IP, or, behind TRUSTED_PROXY_HOPS proxies, the address the outermost trusted proxy saw.

    Counting from the right of X-Forwarded-For is spoof-resistant: clients can only prepend entries.
    """
    peer = http_request.client.host if http_request.client else "unknown"
    if _TRUSTED_PROXY_HOPS <= 0:
        return peer
    hops = [hop.strip() for hop in http_request.headers.get("x-forwarded-for", "").split(",") if hop.strip()]
    return hops[-_TRUSTED_PROXY_HOPS] if len(hops) >= _TRUSTED_PROXY_HOPS else peer


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
