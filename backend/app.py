import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from backend.agent.icp_conversation import run_icp_conversation, infer_icp_signals
from backend.agent.pipeline import run_evaluation_pipeline
from backend.agent.verdict import format_verdict_display

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


@app.post("/analyze")
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run full evaluation pipeline: ICP conversation -> Phase 2 evaluation -> verdict.
    For MVP, we skip the interactive ICP conversation and go straight to evaluation
    with a default ICP profile.
    """
    try:
        # Phase 1 stub - infer signals from product_description until real conversation is wired
        signals = infer_icp_signals(request.product_description)
        icp_profile = {
            "target_company_size": "50-500",
            "funding_stage": ["Series A", "Series B"],
            "tech_signals": signals["tech_signals"],
            "hiring_signals": signals["hiring_signals"],
            "budget_indicator": "mid-market",
            "raw_description": request.product_description,
        }

        # Run evaluation pipeline
        result = run_evaluation_pipeline(
            company_name=request.company_name,
            icp_profile=icp_profile
        )

        # Format response
        verdict = format_verdict_display(result["verdict"])

        evidence = {
            "crunchbase": result["crunchbase"]["summary"],
            "builtwith": result["builtwith"]["summary"],
            "careers": result["careers"]["summary"],
            "web_search": result["web_search"]["summary"],
        }

        return AnalyzeResponse(
            company_name=request.company_name,
            verdict=verdict,
            evidence=evidence
        )

    except Exception as e:
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
