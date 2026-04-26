"""
Agent 2 — Document Parser

Uses GPT-4o vision to extract structured data from medical documents.
Handles messy real-world docs: handwritten prescriptions, blurry bills,
rubber stamps, multilingual text, phone photos.

Input:  ClaimSubmission (documents with content or raw images)
Output: ParsedClaim (structured extraction) + TraceStep
"""
from __future__ import annotations

import json
from typing import Any

from core.models import (
    ClaimSubmission, DocumentInfo, DocumentType,
    DocumentQuality, TraceStep, AgentStatus,
)
from core.config import get_settings


# ── Structured extraction result ─────────────────────────────────────────────

class ParsedDocument:
    def __init__(self, file_id: str, doc_type: DocumentType, fields: dict[str, Any],
                 confidence: float, warnings: list[str]):
        self.file_id = file_id
        self.doc_type = doc_type
        self.fields = fields          # extracted key-value pairs
        self.confidence = confidence  # 0.0 - 1.0
        self.warnings = warnings      # low-confidence fields, partial reads


class ParsedClaim:
    def __init__(self):
        self.patient_name: str | None = None
        self.diagnosis: str | None = None
        self.treatment: str | None = None
        self.doctor_name: str | None = None
        self.doctor_registration: str | None = None
        self.hospital_name: str | None = None
        self.treatment_date: str | None = None
        self.total_amount: float | None = None
        self.line_items: list[dict] = []
        self.medicines: list[str] = []
        self.tests_ordered: list[str] = []
        self.parsed_documents: list[ParsedDocument] = []
        self.overall_confidence: float = 1.0
        self.warnings: list[str] = []


# ── Main agent function ───────────────────────────────────────────────────────

def run_document_parser(
    submission: ClaimSubmission,
    simulate_failure: bool = False,
) -> tuple[ParsedClaim, TraceStep]:
    """
    Extracts structured data from all documents in the submission.
    If content is already structured (test cases), uses it directly.
    If raw image, calls GPT-4o vision.
    """
    if simulate_failure:
        return _simulate_failure(submission)

    parsed = ParsedClaim()
    all_warnings: list[str] = []
    confidence_scores: list[float] = []

    for doc in submission.documents:
        # Skip unreadable docs — verifier already flagged them
        if doc.quality == DocumentQuality.UNREADABLE:
            all_warnings.append(f"{doc.actual_type.value} ({doc.file_id}) skipped — unreadable")
            confidence_scores.append(0.3)
            continue

        # If structured content provided (test cases), extract directly
        if doc.content:
            parsed_doc = _extract_from_structured(doc)
        else:
            # Real upload — call GPT-4o vision with actual file bytes
            parsed_doc = _extract_via_llm(doc, submission, file_bytes=doc.file_bytes)

        parsed.parsed_documents.append(parsed_doc)
        confidence_scores.append(parsed_doc.confidence)
        all_warnings.extend(parsed_doc.warnings)

        # Merge fields into unified ParsedClaim
        _merge_into_claim(parsed, parsed_doc)

    # Overall confidence = average of individual doc confidences
    if confidence_scores:
        parsed.overall_confidence = round(sum(confidence_scores) / len(confidence_scores), 2)
    else:
        parsed.overall_confidence = 0.5

    parsed.warnings = all_warnings

    # Build trace
    status = AgentStatus.SUCCESS if parsed.overall_confidence >= 0.5 else AgentStatus.FAILED
    trace = TraceStep(
        agent="document_parser",
        status=status,
        detail=(
            f"Parsed {len(parsed.parsed_documents)} document(s). "
            f"Patient: {parsed.patient_name or 'not found'}. "
            f"Diagnosis: {parsed.diagnosis or 'not found'}. "
            f"Total: ₹{parsed.total_amount or 0}. "
            f"Confidence: {parsed.overall_confidence}."
            + (f" Warnings: {'; '.join(all_warnings)}" if all_warnings else "")
        ),
        confidence_delta=-(1.0 - parsed.overall_confidence) * 0.3,
        data={
            "patient_name": parsed.patient_name,
            "diagnosis": parsed.diagnosis,
            "total_amount": parsed.total_amount,
            "line_items": parsed.line_items,
            "warnings": all_warnings,
        },
    )

    return parsed, trace


# ── Extract from structured content (test cases) ─────────────────────────────

def _extract_from_structured(doc: DocumentInfo) -> ParsedDocument:
    """
    Test cases provide pre-structured content dicts.
    Extract fields directly without calling the LLM.
    """
    content = doc.content or {}
    warnings: list[str] = []
    confidence = 1.0

    fields: dict[str, Any] = {}

    if doc.actual_type == DocumentType.PRESCRIPTION:
        fields = {
            "patient_name": content.get("patient_name"),
            "doctor_name": content.get("doctor_name"),
            "doctor_registration": content.get("doctor_registration"),
            "diagnosis": content.get("diagnosis"),
            "medicines": content.get("medicines", []),
            "tests_ordered": content.get("tests_ordered", []),
            "date": content.get("date"),
            "treatment": content.get("treatment"),
        }

    elif doc.actual_type == DocumentType.HOSPITAL_BILL:
        fields = {
            "patient_name": content.get("patient_name"),
            "hospital_name": content.get("hospital_name"),
            "date": content.get("date"),
            "line_items": content.get("line_items", []),
            "total": content.get("total", 0),
        }

    elif doc.actual_type == DocumentType.PHARMACY_BILL:
        fields = {
            "patient_name": content.get("patient_name"),
            "medicines": content.get("medicines", []),
            "total": content.get("total", 0),
            "date": content.get("date"),
        }

    elif doc.actual_type == DocumentType.LAB_REPORT:
        fields = {
            "patient_name": content.get("patient_name"),
            "test_name": content.get("test_name"),
            "results": content.get("results", []),
            "date": content.get("date"),
        }

    # Flag missing critical fields
    if not fields.get("patient_name"):
        warnings.append(f"No patient name found in {doc.actual_type.value}")
        confidence -= 0.1

    return ParsedDocument(
        file_id=doc.file_id,
        doc_type=doc.actual_type,
        fields=fields,
        confidence=confidence,
        warnings=warnings,
    )


# ── Extract via GPT-4o vision (real uploads) ──────────────────────────────────

def _extract_via_llm(
    doc: DocumentInfo,
    submission: ClaimSubmission,
    file_bytes: bytes | None = None,
) -> ParsedDocument:
    """
    Calls GPT-4o vision to extract structured fields from a real uploaded document.
    file_bytes: raw bytes of the uploaded file (PDF or image).
    If file_bytes is None, returns a low-confidence empty result.
    """
    try:
        import os
        from openai import OpenAI
        from core.file_handler import process_file, build_vision_content, FileType

        # Load settings fresh — don't rely on cached lru_cache instance
        try:
            settings = get_settings()
            api_key = settings.openai_api_key
            model = settings.openai_model
        except Exception:
            # Fallback: read directly from environment
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.environ.get("OPENAI_API_KEY", "")
            model = os.environ.get("OPENAI_MODEL", "gpt-4o")

        client = OpenAI(api_key=api_key)

        # No file bytes — cannot extract
        if not file_bytes:
            return ParsedDocument(
                file_id=doc.file_id,
                doc_type=doc.actual_type,
                fields={},
                confidence=0.1,
                warnings=[f"No file bytes provided for {doc.file_id} — cannot extract."],
            )

        # Process the file into base64 pages
        file_content = process_file(file_bytes, doc.file_id, doc.file_name or doc.file_id)

        if file_content.error:
            return ParsedDocument(
                file_id=doc.file_id,
                doc_type=doc.actual_type,
                fields={},
                confidence=0.2,
                warnings=[f"File processing error: {file_content.error}"],
            )

        # Adjust doc quality based on blur detection
        quality_warnings = []
        if file_content.quality_label == "UNREADABLE":
            quality_warnings.append(
                f"Document is too blurry to read reliably "
                f"(blur score: {file_content.overall_blur_score:.0f}). "
                f"Please re-upload a clearer photo or scan."
            )
        elif file_content.quality_label == "DEGRADED":
            quality_warnings.append(
                f"Document quality is degraded "
                f"(blur score: {file_content.overall_blur_score:.0f}). "
                f"Some fields may be uncertain."
            )

        # Build vision message with all pages
        prompt = _build_extraction_prompt(doc.actual_type, submission.claim_category.value)
        vision_content = build_vision_content(file_content, prompt)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": vision_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content
        extracted = json.loads(raw)

        confidence = float(extracted.pop("confidence", 0.8))
        # Reduce confidence for degraded documents
        if file_content.quality_label == "UNREADABLE":
            confidence = min(confidence, 0.3)
        elif file_content.quality_label == "DEGRADED":
            confidence = min(confidence, 0.65)

        warnings = extracted.pop("warnings", []) + quality_warnings

        return ParsedDocument(
            file_id=doc.file_id,
            doc_type=doc.actual_type,
            fields=extracted,
            confidence=confidence,
            warnings=warnings,
        )

    except Exception as e:
        return ParsedDocument(
            file_id=doc.file_id,
            doc_type=doc.actual_type,
            fields={},
            confidence=0.2,
            warnings=[f"LLM extraction failed for {doc.file_id}: {str(e)}"],
        )


# ── Merge parsed doc fields into unified claim ────────────────────────────────

def _merge_into_claim(claim: ParsedClaim, doc: ParsedDocument) -> None:
    f = doc.fields

    # Patient name — take first non-null
    if not claim.patient_name:
        claim.patient_name = f.get("patient_name")

    # Diagnosis — from prescription
    if doc.doc_type == DocumentType.PRESCRIPTION:
        if not claim.diagnosis:
            claim.diagnosis = f.get("diagnosis")
        if not claim.doctor_name:
            claim.doctor_name = f.get("doctor_name")
        if not claim.doctor_registration:
            claim.doctor_registration = f.get("doctor_registration")
        claim.medicines.extend(f.get("medicines") or [])
        claim.tests_ordered.extend(f.get("tests_ordered") or [])
        if not claim.treatment:
            claim.treatment = f.get("treatment")

    # Amounts and line items — from bills
    elif doc.doc_type in (DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL):
        if not claim.hospital_name:
            claim.hospital_name = f.get("hospital_name")
        if not claim.treatment_date:
            claim.treatment_date = f.get("date")
        claim.line_items.extend(f.get("line_items") or [])
        total = f.get("total")
        if total:
            claim.total_amount = (claim.total_amount or 0) + float(total)

    # Date
    if not claim.treatment_date and f.get("date"):
        claim.treatment_date = f.get("date")


# ── Graceful degradation for TC011 ───────────────────────────────────────────

def _simulate_failure(submission: ClaimSubmission) -> tuple[ParsedClaim, TraceStep]:
    """
    TC011: simulate this agent failing mid-processing.
    Returns a partial result with low confidence — pipeline must continue.
    """
    parsed = ParsedClaim()
    parsed.overall_confidence = 0.4
    parsed.warnings = ["Document parser failed — component error simulated"]

    # Still extract what we can from structured content
    for doc in submission.documents:
        if doc.content:
            parsed_doc = _extract_from_structured(doc)
            parsed.parsed_documents.append(parsed_doc)
            _merge_into_claim(parsed, parsed_doc)

    trace = TraceStep(
        agent="document_parser",
        status=AgentStatus.FAILED,
        detail="Component failure simulated. Partial extraction only. Manual review recommended.",
        confidence_delta=-0.4,
        data={"simulated_failure": True, "partial_data": parsed.patient_name},
    )
    return parsed, trace


# ── Prompts ───────────────────────────────────────────────────────────────────

def _system_prompt() -> str:
    return """You are a medical document extraction specialist for Indian health insurance claims.
Extract structured information from medical documents and return ONLY valid JSON.
Handle: handwritten prescriptions, rubber stamps, phone photos, multilingual text.
For unclear fields, include them with low confidence rather than omitting them.
Always include a 'confidence' float (0.0-1.0) and a 'warnings' list in your response."""


def _build_extraction_prompt(doc_type: DocumentType, claim_category: str) -> str:
    prompts = {
        DocumentType.PRESCRIPTION: """Extract from this Indian medical prescription:
{
  "patient_name": "full name",
  "doctor_name": "Dr. name with title",
  "doctor_registration": "state registration number e.g. KA/45678/2015",
  "diagnosis": "primary diagnosis",
  "medicines": ["medicine name dosage"],
  "tests_ordered": ["test names"],
  "date": "YYYY-MM-DD",
  "confidence": 0.9,
  "warnings": ["any unclear fields"]
}""",
        DocumentType.HOSPITAL_BILL: """Extract from this Indian hospital/clinic bill:
{
  "patient_name": "full name",
  "hospital_name": "hospital or clinic name",
  "date": "YYYY-MM-DD",
  "line_items": [{"description": "item", "amount": 0}],
  "total": 0,
  "confidence": 0.9,
  "warnings": ["any unclear fields"]
}""",
        DocumentType.PHARMACY_BILL: """Extract from this Indian pharmacy bill:
{
  "patient_name": "full name",
  "medicines": [{"name": "medicine", "amount": 0}],
  "total": 0,
  "date": "YYYY-MM-DD",
  "confidence": 0.9,
  "warnings": []
}""",
        DocumentType.LAB_REPORT: """Extract from this Indian lab report:
{
  "patient_name": "full name",
  "test_name": "primary test name",
  "results": [{"test": "name", "result": "value", "normal_range": "range"}],
  "date": "YYYY-MM-DD",
  "confidence": 0.9,
  "warnings": []
}""",
    }
    return prompts.get(doc_type, f"Extract all relevant medical information from this {doc_type.value} document. Return as JSON with confidence and warnings fields.")