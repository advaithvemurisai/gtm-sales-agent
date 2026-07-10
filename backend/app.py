import logging
import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from backend.agent.icp_conversation import run_icp_conversation, infer_icp_signals
from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gtm_agent.api")

load_dotenv()

app = FastAPI(title="GTM Sales Intelligence Agent")

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    company_name: str
    product_description: str


class ChatRequest(BaseModel):
    company_name: str
    product_description: str
    message: str


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
        }

        summary = {
            "decision": verdict["decision"],
            "signal_count": len(verdict.get("signals", [])),
            "reasoning_preview": verdict.get("reasoning", "")[:220],
            "evidence_sources": ["company_signals", "builtwith", "careers", "web_search"],
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
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    """
    Handle ICP conversation messages (Phase 1).
    For MVP, this is a placeholder that returns the message back.
    """
    # TODO: Implement interactive ICP conversation
    return {
        "message": f"You said: {request.message}",
        "phase": "icp"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
