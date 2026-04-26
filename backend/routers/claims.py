from fastapi import APIRouter, HTTPException
from core.models import ClaimSubmission
from agents.pipeline import run_pipeline

router = APIRouter()


@router.post("/claims", response_model=dict)
async def submit_claim(submission: ClaimSubmission):
    """
    Full claims pipeline endpoint - JSON version.
    Accepts pre-structured content dicts instead of file uploads.
    Used for programmatic testing and Swagger demos.
    Runs: verifier -> parser -> evaluator -> fraud -> synthesizer
    Always returns - never crashes.
    """
    result = run_pipeline(submission)

    if result["status"] == "document_verification_failed":
        raise HTTPException(
            status_code=422,
            detail={
                "stage": "document_verification",
                "errors": result["errors"],
                "trace": result["trace"],
                "message": "Document verification failed. See errors for details.",
            },
        )

    return result