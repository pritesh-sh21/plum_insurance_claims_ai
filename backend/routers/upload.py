"""
routers/upload.py

POST /api/v1/claims/upload

Accepts multipart/form-data with:
  - claim metadata as form fields
  - one or more uploaded files (PDFs or images)
  - document_types: JSON array matching files order
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from agents.pipeline import run_pipeline
from core.file_handler import process_file
from core.models import (
    ClaimSubmission, ClaimCategory, DocumentInfo,
    DocumentType, DocumentQuality,
)

router = APIRouter()

_NAME_TO_TYPE: dict[str, DocumentType] = {
    "prescription": DocumentType.PRESCRIPTION,
    "rx":           DocumentType.PRESCRIPTION,
    "bill":         DocumentType.HOSPITAL_BILL,
    "invoice":      DocumentType.HOSPITAL_BILL,
    "lab":          DocumentType.LAB_REPORT,
    "report":       DocumentType.LAB_REPORT,
    "pharmacy":     DocumentType.PHARMACY_BILL,
    "dental":       DocumentType.DENTAL_REPORT,
    "discharge":    DocumentType.DISCHARGE_SUMMARY,
}


@router.post("/claims/upload")
async def upload_claim(
    member_id:          Annotated[str,   Form()],
    policy_id:          Annotated[str,   Form()],
    claim_category:     Annotated[str,   Form()],
    treatment_date:     Annotated[str,   Form()],
    claimed_amount:     Annotated[float, Form()],
    hospital_name:      Annotated[str,   Form()] = "",
    ytd_claims_amount:  Annotated[float, Form()] = 0.0,
    document_types:     Annotated[str,   Form()] = "[]",
    files: list[UploadFile] = File(default=[]),
):
    # Parse document type hints
    try:
        doc_type_hints: list[str] = json.loads(document_types)
    except Exception:
        doc_type_hints = []

    print(f"[upload] member={member_id} category={claim_category}")
    print(f"[upload] doc_type_hints={doc_type_hints}")
    print(f"[upload] files={[f.filename for f in files]}")

    documents: list[DocumentInfo] = []

    for i, upload in enumerate(files):
        file_bytes = await upload.read()
        file_id   = f"F{str(i + 1).zfill(3)}"
        file_name = upload.filename or f"document_{i + 1}"

        # Resolve document type from UI hint first, then filename
        doc_type = _resolve_doc_type(doc_type_hints, i, file_name)
        print(f"[upload] file[{i}] {file_name} → {doc_type}")

        # Try to detect quality via blur score
        quality = DocumentQuality.GOOD
        try:
            file_content = process_file(file_bytes, file_id, file_name)
            if not file_content.error:
                quality = _map_quality(file_content.quality_label)
        except Exception as e:
            print(f"[upload] file processing warning for {file_name}: {e}")
            quality = DocumentQuality.GOOD  # don't penalise on processing error

        documents.append(DocumentInfo(
            file_id=file_id,
            file_name=file_name,
            actual_type=doc_type,
            quality=quality,
            file_bytes=file_bytes,
        ))

    if not documents:
        raise HTTPException(status_code=422, detail="No files uploaded.")

    try:
        submission = ClaimSubmission(
            member_id=member_id,
            policy_id=policy_id,
            claim_category=ClaimCategory(claim_category),
            treatment_date=treatment_date,
            claimed_amount=claimed_amount,
            hospital_name=hospital_name or None,
            ytd_claims_amount=ytd_claims_amount,
            documents=documents,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid claim data: {str(e)}")

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


def _resolve_doc_type(hints: list[str], index: int, file_name: str) -> DocumentType:
    # UI hint takes priority
    if index < len(hints):
        try:
            return DocumentType(hints[index])
        except ValueError:
            pass

    # Filename keyword fallback
    name_lower = file_name.lower()
    for keyword, doc_type in _NAME_TO_TYPE.items():
        if keyword in name_lower:
            return doc_type

    return DocumentType.UNKNOWN


def _map_quality(quality_label: str) -> DocumentQuality:
    return {
        "GOOD":      DocumentQuality.GOOD,
        "DEGRADED":  DocumentQuality.DEGRADED,
        "UNREADABLE":DocumentQuality.UNREADABLE,
    }.get(quality_label, DocumentQuality.GOOD)