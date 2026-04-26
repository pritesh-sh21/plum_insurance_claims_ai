import uuid
from fastapi import APIRouter, HTTPException
from core.models import ClaimSubmission, ClaimDecision, DecisionType
from agents.verifier import run_document_verifier

router = APIRouter()


@router.post("/claims", response_model=dict)
async def submit_claim(submission: ClaimSubmission):
    """
    Main claims endpoint. Runs the full agent pipeline.
    Phase 1: document verifier only. Remaining agents coming in Phase 2.
    """
    claim_id = str(uuid.uuid4())[:8].upper()

    # ── Agent 1: Document verifier ────────────────────────────────────────────
    errors, verifier_trace = run_document_verifier(submission)

    if errors:
        # Return 422 with specific, actionable errors — never a generic message
        raise HTTPException(
            status_code=422,
            detail={
                "claim_id": claim_id,
                "stage": "document_verification",
                "errors": [e.model_dump() for e in errors],
                "trace": [verifier_trace.model_dump()],
                "message": "Document verification failed. See errors for details.",
            },
        )

    # ── Placeholder: Agents 2–5 will be wired in Phase 2 ─────────────────────
    return {
        "claim_id": claim_id,
        "status": "documents_verified",
        "message": "Documents passed verification. Processing pipeline coming in Phase 2.",
        "trace": [verifier_trace.model_dump()],
    }
