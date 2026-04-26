"""
Pipeline tests — TC004 through TC012.
Uses run_pipeline() directly without HTTP layer.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from core.models import (
    ClaimSubmission, DocumentInfo, ClaimCategory,
    DocumentType, DocumentQuality, ClaimsHistory,
)
from agents.pipeline import run_pipeline


# ── TC004: Clean consultation — full approval ─────────────────────────────────

def test_tc004_clean_consultation():
    submission = ClaimSubmission(
        member_id="EMP001", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-01", claimed_amount=1500,
        ytd_claims_amount=5000,
        documents=[
            DocumentInfo(file_id="F007", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Dr. Arun Sharma",
                         "doctor_registration": "KA/45678/2015",
                         "patient_name": "Rajesh Kumar",
                         "date": "2024-11-01", "diagnosis": "Viral Fever",
                         "medicines": ["Paracetamol 650mg", "Vitamin C 500mg"]}),
            DocumentInfo(file_id="F008", actual_type=DocumentType.HOSPITAL_BILL,
                content={"hospital_name": "City Clinic, Bengaluru",
                         "patient_name": "Rajesh Kumar", "date": "2024-11-01",
                         "line_items": [{"description": "Consultation Fee", "amount": 1000},
                                        {"description": "CBC Test", "amount": 300},
                                        {"description": "Dengue NS1 Test", "amount": 200}],
                         "total": 1500}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "APPROVED", f"Expected APPROVED, got {result['decision']}"
    assert result["approved_amount"] == 1350.0, f"Expected ₹1350 (10% copay), got {result['approved_amount']}"
    assert result["confidence_score"] >= 0.85, f"Confidence too low: {result['confidence_score']}"


# ── TC005: Waiting period — diabetes ─────────────────────────────────────────

def test_tc005_diabetes_waiting_period():
    submission = ClaimSubmission(
        member_id="EMP005", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-10-15", claimed_amount=3000,
        documents=[
            DocumentInfo(file_id="F009", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Dr. Sunil Mehta",
                         "doctor_registration": "GJ/56789/2014",
                         "patient_name": "Vikram Joshi",
                         "diagnosis": "Type 2 Diabetes Mellitus",
                         "medicines": ["Metformin 500mg", "Glimepiride 1mg"]}),
            DocumentInfo(file_id="F010", actual_type=DocumentType.HOSPITAL_BILL,
                content={"patient_name": "Vikram Joshi",
                         "date": "2024-10-15", "total": 3000}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "REJECTED", f"Expected REJECTED, got {result['decision']}"
    assert "WAITING_PERIOD" in result["rejection_reasons"]
    # Must state when eligible
    assert "2024-11-30" in result["message"] or "eligible" in result["message"].lower()


# ── TC006: Dental partial approval ───────────────────────────────────────────

def test_tc006_dental_partial():
    submission = ClaimSubmission(
        member_id="EMP002", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.DENTAL,
        treatment_date="2024-10-15", claimed_amount=12000,
        documents=[
            DocumentInfo(file_id="F011", actual_type=DocumentType.HOSPITAL_BILL,
                content={"hospital_name": "Smile Dental Clinic",
                         "patient_name": "Priya Singh",
                         "line_items": [
                             {"description": "Root Canal Treatment", "amount": 8000},
                             {"description": "Teeth Whitening", "amount": 4000},
                         ],
                         "total": 12000}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "PARTIAL", f"Expected PARTIAL, got {result['decision']}"
    assert result["approved_amount"] == 8000.0, f"Expected ₹8000 approved, got {result['approved_amount']}"
    # Must itemize
    li = result["line_item_decisions"]
    approved = [x for x in li if x["approved_amount"] > 0]
    rejected = [x for x in li if x["approved_amount"] == 0]
    assert any("Root Canal" in x["description"] for x in approved)
    assert any("Whitening" in x["description"] for x in rejected)


# ── TC007: MRI without pre-auth ───────────────────────────────────────────────

def test_tc007_mri_no_preauth():
    submission = ClaimSubmission(
        member_id="EMP007", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.DIAGNOSTIC,
        treatment_date="2024-11-02", claimed_amount=15000,
        documents=[
            DocumentInfo(file_id="F012", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Dr. Venkat Rao",
                         "doctor_registration": "AP/67890/2017",
                         "diagnosis": "Suspected Lumbar Disc Herniation",
                         "tests_ordered": ["MRI Lumbar Spine"]}),
            DocumentInfo(file_id="F013", actual_type=DocumentType.LAB_REPORT,
                content={"test_name": "MRI Lumbar Spine"}),
            DocumentInfo(file_id="F014", actual_type=DocumentType.HOSPITAL_BILL,
                content={"line_items": [{"description": "MRI Lumbar Spine", "amount": 15000}],
                         "total": 15000}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "REJECTED", f"Expected REJECTED, got {result['decision']}"
    assert "PRE_AUTH_MISSING" in result["rejection_reasons"]
    assert "pre-auth" in result["message"].lower() or "pre-authorization" in result["message"].lower()


# ── TC008: Per-claim limit exceeded ──────────────────────────────────────────

def test_tc008_per_claim_exceeded():
    submission = ClaimSubmission(
        member_id="EMP003", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-10-20", claimed_amount=7500,
        ytd_claims_amount=10000,
        documents=[
            DocumentInfo(file_id="F015", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Dr. R. Gupta",
                         "doctor_registration": "DL/34567/2016",
                         "diagnosis": "Gastroenteritis",
                         "medicines": ["Antibiotics", "Probiotics", "ORS"]}),
            DocumentInfo(file_id="F016", actual_type=DocumentType.HOSPITAL_BILL,
                content={"line_items": [{"description": "Consultation Fee", "amount": 2000},
                                        {"description": "Medicines", "amount": 5500}],
                         "total": 7500}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "REJECTED", f"Expected REJECTED, got {result['decision']}"
    assert "PER_CLAIM_EXCEEDED" in result["rejection_reasons"]
    assert "7,500" in result["message"] or "7500" in result["message"]
    assert "5,000" in result["message"] or "5000" in result["message"]


# ── TC009: Fraud — multiple same-day claims ───────────────────────────────────

def test_tc009_fraud_same_day():
    submission = ClaimSubmission(
        member_id="EMP008", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-10-30", claimed_amount=4800,
        claims_history=[
            ClaimsHistory(claim_id="CLM_0081", date="2024-10-30", amount=1200, provider="City Clinic A"),
            ClaimsHistory(claim_id="CLM_0082", date="2024-10-30", amount=1800, provider="City Clinic B"),
            ClaimsHistory(claim_id="CLM_0083", date="2024-10-30", amount=2100, provider="Wellness Center"),
        ],
        documents=[
            DocumentInfo(file_id="F017", actual_type=DocumentType.PRESCRIPTION,
                content={"diagnosis": "Migraine", "doctor_name": "Dr. S. Khan"}),
            DocumentInfo(file_id="F018", actual_type=DocumentType.HOSPITAL_BILL,
                content={"total": 4800}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "MANUAL_REVIEW", f"Expected MANUAL_REVIEW, got {result['decision']}"
    # Must include fraud signal details
    assert any("same-day" in t["detail"].lower() or "2024-10-30" in t["detail"]
               for t in result["trace"])


# ── TC010: Network hospital — discount applied ────────────────────────────────

def test_tc010_network_hospital():
    submission = ClaimSubmission(
        member_id="EMP010", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-11-03", claimed_amount=4500,
        hospital_name="Apollo Hospitals",
        ytd_claims_amount=8000,
        documents=[
            DocumentInfo(file_id="F019", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Dr. S. Iyer",
                         "doctor_registration": "TN/56789/2013",
                         "patient_name": "Deepak Shah",
                         "diagnosis": "Acute Bronchitis",
                         "medicines": ["Amoxicillin 500mg", "Salbutamol Inhaler"]}),
            DocumentInfo(file_id="F020", actual_type=DocumentType.HOSPITAL_BILL,
                content={"hospital_name": "Apollo Hospitals",
                         "patient_name": "Deepak Shah",
                         "line_items": [{"description": "Consultation Fee", "amount": 1500},
                                        {"description": "Medicines", "amount": 3000}],
                         "total": 4500}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "APPROVED", f"Expected APPROVED, got {result['decision']}"
    assert result["approved_amount"] == 3240.0, f"Expected ₹3240, got {result['approved_amount']}"
    # Must show breakdown
    breakdown = result.get("calculation_breakdown", {})
    assert breakdown.get("network_discount") == 900.0
    assert breakdown.get("copay") == 360.0


# ── TC011: Component failure — graceful degradation ──────────────────────────

def test_tc011_graceful_degradation():
    submission = ClaimSubmission(
        member_id="EMP006", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.ALTERNATIVE_MEDICINE,
        treatment_date="2024-10-28", claimed_amount=4000,
        simulate_component_failure=True,
        documents=[
            DocumentInfo(file_id="F021", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Vaidya T. Krishnan",
                         "doctor_registration": "AYUR/KL/2345/2019",
                         "diagnosis": "Chronic Joint Pain",
                         "treatment": "Panchakarma Therapy"}),
            DocumentInfo(file_id="F022", actual_type=DocumentType.HOSPITAL_BILL,
                content={"hospital_name": "Ayur Wellness Centre", "total": 4000,
                         "line_items": [{"description": "Panchakarma Therapy (5 sessions)", "amount": 3000},
                                        {"description": "Consultation", "amount": 1000}]}),
        ],
    )
    result = run_pipeline(submission)
    # Must not crash
    assert result is not None
    # Must produce a decision
    assert result.get("decision") in ["APPROVED", "MANUAL_REVIEW"]
    # Confidence must be lower than normal
    assert result["confidence_score"] < 0.85, f"Confidence should be reduced: {result['confidence_score']}"
    # Must indicate component failure
    assert len(result.get("component_failures", [])) > 0 or result.get("manual_review_recommended")
    # Must recommend manual review
    assert result.get("manual_review_recommended") is True


# ── TC012: Excluded treatment ─────────────────────────────────────────────────

def test_tc012_excluded_treatment():
    submission = ClaimSubmission(
        member_id="EMP009", policy_id="PLUM_GHI_2024",
        claim_category=ClaimCategory.CONSULTATION,
        treatment_date="2024-10-18", claimed_amount=8000,
        documents=[
            DocumentInfo(file_id="F023", actual_type=DocumentType.PRESCRIPTION,
                content={"doctor_name": "Dr. P. Banerjee",
                         "doctor_registration": "WB/34567/2015",
                         "diagnosis": "Morbid Obesity — BMI 37",
                         "treatment": "Bariatric Consultation and Customised Diet Plan"}),
            DocumentInfo(file_id="F024", actual_type=DocumentType.HOSPITAL_BILL,
                content={"line_items": [{"description": "Bariatric Consultation", "amount": 3000},
                                        {"description": "Personalised Diet and Nutrition Program", "amount": 5000}],
                         "total": 8000}),
        ],
    )
    result = run_pipeline(submission)
    assert result["decision"] == "REJECTED", f"Expected REJECTED, got {result['decision']}"
    assert "EXCLUDED_CONDITION" in result["rejection_reasons"]
    assert result["confidence_score"] >= 0.90, f"Confidence should be high: {result['confidence_score']}"
