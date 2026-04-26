"""
Agent 1 — Document Verifier

Runs BEFORE any LLM extraction or policy evaluation.
If it finds a problem it returns immediately with a specific, actionable error.
Never returns a generic message.

Covers:
  TC001 — wrong document type uploaded
  TC002 — unreadable document
  TC003 — documents belong to different patients
"""
from __future__ import annotations

from core.models import (
    ClaimSubmission,
    DocumentInfo,
    DocumentType,
    DocumentQuality,
    DocumentVerificationError,
    TraceStep,
    AgentStatus,
)
from core.policy_engine import get_required_documents


def run_document_verifier(
    submission: ClaimSubmission,
) -> tuple[list[DocumentVerificationError], TraceStep]:
    """
    Returns (errors, trace_step).
    errors is empty if all documents are valid.
    """
    errors: list[DocumentVerificationError] = []

    # ── Check 1: required document types present (TC001) ─────────────────────
    required = get_required_documents(submission.claim_category)
    uploaded_types = [doc.actual_type for doc in submission.documents]

    for req_type in required:
        if req_type not in uploaded_types:
            # Find what was uploaded instead (helpful for the error message)
            wrong_docs = [
                doc for doc in submission.documents
                if doc.actual_type != req_type and doc.actual_type != DocumentType.UNKNOWN
            ]
            wrong_type_str = (
                wrong_docs[0].actual_type.value if wrong_docs else "UNKNOWN"
            )
            errors.append(DocumentVerificationError(
                error_code="WRONG_DOCUMENT_TYPE",
                message=(
                    f"Your {submission.claim_category.value} claim requires a "
                    f"{_friendly(req_type)}, but we received a "
                    f"{_friendly_str(wrong_type_str)} instead. "
                    f"Please re-upload the correct document."
                ),
                uploaded_type=wrong_docs[0].actual_type if wrong_docs else None,
                required_types=[req_type],
            ))

    # ── Check 2: unreadable documents (TC002) ─────────────────────────────────
    for doc in submission.documents:
        if doc.quality == DocumentQuality.UNREADABLE:
            errors.append(DocumentVerificationError(
                error_code="UNREADABLE_DOCUMENT",
                message=(
                    f"The {_friendly(doc.actual_type)} you uploaded "
                    f"(file: {doc.file_name or doc.file_id}) is too blurry or "
                    f"unclear to read. Please re-upload a clearer photo or scan. "
                    f"Your claim has not been rejected — just re-upload this document."
                ),
                file_id=doc.file_id,
                uploaded_type=doc.actual_type,
            ))

    # ── Check 3: documents belong to different patients (TC003) ───────────────
    patient_names = _extract_patient_names(submission.documents)
    if len(patient_names) > 1:
        name_list = ", ".join(
            f"{doc.actual_type.value}: '{patient_names[doc.file_id]}'"
            for doc in submission.documents
            if doc.file_id in patient_names
        )
        errors.append(DocumentVerificationError(
            error_code="PATIENT_MISMATCH",
            message=(
                f"Your documents appear to belong to different people. "
                f"We found: {name_list}. "
                f"Please ensure all documents are for the same patient."
            ),
            details={"names_found": patient_names},
        ))

    # ── Build trace step ──────────────────────────────────────────────────────
    if errors:
        trace = TraceStep(
            agent="document_verifier",
            status=AgentStatus.FAILED,
            detail=f"{len(errors)} verification error(s): "
                   + " | ".join(e.error_code for e in errors),
            confidence_delta=-1.0,
        )
    else:
        trace = TraceStep(
            agent="document_verifier",
            status=AgentStatus.SUCCESS,
            detail=(
                f"All {len(submission.documents)} document(s) verified. "
                f"Types: {[d.actual_type.value for d in submission.documents]}"
            ),
            confidence_delta=0.0,
        )

    return errors, trace


# ── Helpers ───────────────────────────────────────────────────────────────────

def _friendly(doc_type: DocumentType) -> str:
    mapping = {
        DocumentType.PRESCRIPTION: "doctor's prescription (Rx)",
        DocumentType.HOSPITAL_BILL: "hospital or clinic bill",
        DocumentType.LAB_REPORT: "lab / diagnostic report",
        DocumentType.PHARMACY_BILL: "pharmacy bill",
        DocumentType.DENTAL_REPORT: "dental treatment report",
        DocumentType.DISCHARGE_SUMMARY: "discharge summary",
        DocumentType.UNKNOWN: "unrecognized document",
    }
    return mapping.get(doc_type, doc_type.value)


def _friendly_str(type_str: str) -> str:
    try:
        return _friendly(DocumentType(type_str))
    except ValueError:
        return type_str


def _extract_patient_names(
    documents: list[DocumentInfo],
) -> dict[str, str]:
    """Return {file_id: patient_name} for docs that carry a patient name."""
    named: dict[str, str] = {}
    for doc in documents:
        name = doc.patient_name_on_doc
        if not name and doc.content:
            name = doc.content.get("patient_name")
        if name:
            named[doc.file_id] = name.strip().lower()

    # Only flag mismatch if there are 2+ distinct names
    unique_names = set(named.values())
    if len(unique_names) <= 1:
        return {}
    return named
