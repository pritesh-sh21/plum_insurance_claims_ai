"""
Tests for Agent 1 — Document Verifier
Covers TC001, TC002, TC003 from test_cases.json
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from core.models import (
    ClaimSubmission, DocumentInfo, ClaimCategory,
    DocumentType, DocumentQuality, AgentStatus,
)
from agents.verifier import run_document_verifier


# ── TC001: Wrong document uploaded ───────────────────────────────────────────

def test_tc001_wrong_document_type():
    """
    Member submits two prescriptions for a CONSULTATION claim.
    CONSULTATION requires PRESCRIPTION + HOSPITAL_BILL.
    System must name both the uploaded type and the required type.
    """
    submission = ClaimSubmission(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-01",
        claimed_amount=1500,
        documents=[
            DocumentInfo(file_id="F001", file_name="dr_sharma_prescription.jpg",
                         actual_type=DocumentType.PRESCRIPTION),
            DocumentInfo(file_id="F002", file_name="another_prescription.jpg",
                         actual_type=DocumentType.PRESCRIPTION),
        ],
    )
    errors, trace = run_document_verifier(submission)

    assert len(errors) > 0, "Should have caught the wrong document type"
    assert trace.status == AgentStatus.FAILED

    error = errors[0]
    assert error.error_code == "WRONG_DOCUMENT_TYPE"
    # Must name the required type — not a generic message
    assert "HOSPITAL_BILL" in error.message or "hospital" in error.message.lower(), \
        f"Error must name the required document. Got: {error.message}"
    # Must name what was uploaded
    assert "prescription" in error.message.lower(), \
        f"Error must name the uploaded type. Got: {error.message}"


# ── TC002: Unreadable document ────────────────────────────────────────────────

def test_tc002_unreadable_document():
    """
    Prescription is fine but pharmacy bill is unreadable.
    System must ask for re-upload of that specific document — not reject the claim.
    """
    submission = ClaimSubmission(
        member_id="EMP004",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.PHARMACY,
        treatment_date="2024-10-25",
        claimed_amount=800,
        documents=[
            DocumentInfo(file_id="F003", file_name="prescription.jpg",
                         actual_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
            DocumentInfo(file_id="F004", file_name="blurry_bill.jpg",
                         actual_type=DocumentType.PHARMACY_BILL,
                         quality=DocumentQuality.UNREADABLE),
        ],
    )
    errors, trace = run_document_verifier(submission)

    assert len(errors) > 0, "Should have caught the unreadable document"
    assert trace.status == AgentStatus.FAILED

    unreadable_errors = [e for e in errors if e.error_code == "UNREADABLE_DOCUMENT"]
    assert len(unreadable_errors) > 0, "Should have UNREADABLE_DOCUMENT error"

    error = unreadable_errors[0]
    # Must reference the specific file
    assert "blurry_bill.jpg" in error.message or "F004" in error.message, \
        f"Error must reference the specific file. Got: {error.message}"
    # Must NOT declare claim as rejected ("not been rejected" is fine and reassuring)
    msg = error.message.lower()
    assert "claim is rejected" not in msg and not msg.startswith("rejected"),         f"Error must not declare the claim rejected. Got: {error.message}"
    # Must say re-upload
    assert "re-upload" in error.message.lower() or "upload" in error.message.lower(), \
        f"Error must ask for re-upload. Got: {error.message}"


# ── TC003: Documents belong to different patients ─────────────────────────────

def test_tc003_patient_mismatch():
    """
    Prescription is for Rajesh Kumar but bill is for Arjun Mehta.
    System must detect this and name both patients.
    """
    submission = ClaimSubmission(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-01",
        claimed_amount=1500,
        documents=[
            DocumentInfo(file_id="F005", file_name="prescription_rajesh.jpg",
                         actual_type=DocumentType.PRESCRIPTION,
                         patient_name_on_doc="Rajesh Kumar"),
            DocumentInfo(file_id="F006", file_name="bill_arjun.jpg",
                         actual_type=DocumentType.HOSPITAL_BILL,
                         patient_name_on_doc="Arjun Mehta"),
        ],
    )
    errors, trace = run_document_verifier(submission)

    assert len(errors) > 0, "Should have caught the patient mismatch"
    assert trace.status == AgentStatus.FAILED

    mismatch_errors = [e for e in errors if e.error_code == "PATIENT_MISMATCH"]
    assert len(mismatch_errors) > 0, "Should have PATIENT_MISMATCH error"

    error = mismatch_errors[0]
    # Must name both patients found
    assert "rajesh" in error.message.lower(), \
        f"Error must name Rajesh Kumar. Got: {error.message}"
    assert "arjun" in error.message.lower(), \
        f"Error must name Arjun Mehta. Got: {error.message}"


# ── Happy path: valid documents pass through ──────────────────────────────────

def test_valid_documents_pass():
    """
    Correct documents for a CONSULTATION claim should produce no errors.
    """
    submission = ClaimSubmission(
        member_id="EMP001",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-01",
        claimed_amount=1500,
        documents=[
            DocumentInfo(file_id="F007", file_name="prescription.jpg",
                         actual_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD,
                         patient_name_on_doc="Rajesh Kumar"),
            DocumentInfo(file_id="F008", file_name="bill.jpg",
                         actual_type=DocumentType.HOSPITAL_BILL,
                         quality=DocumentQuality.GOOD,
                         patient_name_on_doc="Rajesh Kumar"),
        ],
    )
    errors, trace = run_document_verifier(submission)

    assert len(errors) == 0, f"Valid documents should pass. Errors: {errors}"
    assert trace.status == AgentStatus.SUCCESS


def test_valid_pharmacy_documents_pass():
    """PHARMACY requires PRESCRIPTION + PHARMACY_BILL."""
    submission = ClaimSubmission(
        member_id="EMP004",
        policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.PHARMACY,
        treatment_date="2024-10-25",
        claimed_amount=800,
        documents=[
            DocumentInfo(file_id="F009", actual_type=DocumentType.PRESCRIPTION,
                         quality=DocumentQuality.GOOD),
            DocumentInfo(file_id="F010", actual_type=DocumentType.PHARMACY_BILL,
                         quality=DocumentQuality.GOOD),
        ],
    )
    errors, trace = run_document_verifier(submission)

    assert len(errors) == 0
    assert trace.status == AgentStatus.SUCCESS
