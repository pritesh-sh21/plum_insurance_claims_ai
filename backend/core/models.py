from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    LAB_REPORT = "LAB_REPORT"
    PHARMACY_BILL = "PHARMACY_BILL"
    DENTAL_REPORT = "DENTAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    UNREADABLE = "UNREADABLE"


class DecisionType(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"
    DOCUMENT_MISMATCH = "DOCUMENT_MISMATCH"
    FRAUD_SIGNAL = "FRAUD_SIGNAL"
    SUB_LIMIT_EXCEEDED = "SUB_LIMIT_EXCEEDED"


class AgentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ── Input models ─────────────────────────────────────────────────────────────

class DocumentInfo(BaseModel):
    file_id: str
    file_name: str = ""
    actual_type: DocumentType = DocumentType.UNKNOWN
    quality: DocumentQuality = DocumentQuality.GOOD
    patient_name_on_doc: str | None = None
    content: dict[str, Any] | None = None
    file_bytes: bytes | None = None  # raw upload bytes for real file processing

    model_config = {"arbitrary_types_allowed": True}


class ClaimsHistory(BaseModel):
    claim_id: str
    date: str
    amount: float
    provider: str


class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: str
    claimed_amount: float
    hospital_name: str | None = None
    ytd_claims_amount: float = 0.0
    claims_history: list[ClaimsHistory] = Field(default_factory=list)
    documents: list[DocumentInfo] = Field(default_factory=list)
    simulate_component_failure: bool = False


# ── Trace / observability models ─────────────────────────────────────────────

class TraceStep(BaseModel):
    agent: str
    status: AgentStatus
    detail: str
    confidence_delta: float = 0.0
    data: dict[str, Any] | None = None


# ── Verification error model (TC001, TC002, TC003) ────────────────────────────

class DocumentVerificationError(BaseModel):
    error_code: str
    message: str
    file_id: str | None = None
    uploaded_type: DocumentType | None = None
    required_types: list[DocumentType] | None = None
    details: dict[str, Any] | None = None


# ── Line-item level decision (TC006 dental partial) ───────────────────────────

class LineItemDecision(BaseModel):
    description: str
    claimed_amount: float
    approved_amount: float
    reason: str


# ── Final claim decision ──────────────────────────────────────────────────────

class ClaimDecision(BaseModel):
    claim_id: str
    member_id: str
    decision: DecisionType
    approved_amount: float = 0.0
    claimed_amount: float
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    line_item_decisions: list[LineItemDecision] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0)
    message: str
    trace: list[TraceStep] = Field(default_factory=list)
    component_failures: list[str] = Field(default_factory=list)
    manual_review_recommended: bool = False
    calculation_breakdown: dict[str, Any] | None = None