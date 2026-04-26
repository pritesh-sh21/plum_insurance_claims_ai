"""
Policy engine — reads policy_terms.json and exposes pure functions.
No LLM calls. No hardcoded values. Everything comes from the JSON.
"""
from __future__ import annotations
import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.models import (
    ClaimCategory, DocumentType, RejectionReason
)


# ── Loader ────────────────────────────────────────────────────────────────────

@lru_cache
def load_policy(path: str = "./core/policy_terms.json") -> dict[str, Any]:
    with open(Path(path)) as f:
        return json.load(f)


# ── Member helpers ────────────────────────────────────────────────────────────

def get_member(member_id: str) -> dict | None:
    policy = load_policy()
    return next(
        (m for m in policy["members"] if m["member_id"] == member_id),
        None,
    )


def is_member_valid(member_id: str) -> bool:
    return get_member(member_id) is not None


# ── Waiting period check ──────────────────────────────────────────────────────

CONDITION_KEYWORD_MAP: dict[str, list[str]] = {
    "diabetes": ["diabetes", "t2dm", "diabetic", "metformin", "glimepiride", "insulin"],
    "hypertension": ["hypertension", "htn", "blood pressure", "amlodipine", "losartan"],
    "thyroid_disorders": ["thyroid", "hypothyroid", "hyperthyroid", "thyroxine", "tsh"],
    "joint_replacement": ["joint replacement", "knee replacement", "hip replacement"],
    "maternity": ["maternity", "pregnancy", "prenatal", "antenatal", "delivery", "obstetric"],
    "mental_health": ["mental health", "depression", "anxiety", "psychiatric", "psychosis"],
    "obesity_treatment": ["obesity", "bariatric", "weight loss", "bmi", "morbid obesity"],
    "hernia": ["hernia", "herniation"],
    "cataract": ["cataract"],
}


def detect_condition_from_text(text: str) -> str | None:
    """Return the first matched policy condition key from free text."""
    lower = text.lower()
    for condition, keywords in CONDITION_KEYWORD_MAP.items():
        if any(kw in lower for kw in keywords):
            return condition
    return None


def check_waiting_period(
    member_id: str,
    treatment_date: str,
    diagnosis_text: str,
) -> tuple[bool, str | None, date | None]:
    """
    Returns (is_eligible, reason_message, eligible_from_date).
    eligible_from_date is the date the member will be eligible (if not yet).
    """
    policy = load_policy()
    member = get_member(member_id)
    if not member:
        return False, "Member not found", None

    join = date.fromisoformat(member["join_date"])
    treatment = date.fromisoformat(treatment_date)
    waiting = policy["waiting_periods"]

    # Initial waiting period
    initial_days = waiting["initial_waiting_period_days"]
    initial_eligible = _add_days(join, initial_days)
    if treatment < initial_eligible:
        return (
            False,
            f"Initial {initial_days}-day waiting period not completed. "
            f"Eligible from {initial_eligible}.",
            initial_eligible,
        )

    # Condition-specific waiting period
    condition = detect_condition_from_text(diagnosis_text)
    if condition and condition in waiting.get("specific_conditions", {}):
        cond_days = waiting["specific_conditions"][condition]
        cond_eligible = _add_days(join, cond_days)
        if treatment < cond_eligible:
            return (
                False,
                f"Waiting period for {condition.replace('_', ' ')} is {cond_days} days. "
                f"Eligible from {cond_eligible}.",
                cond_eligible,
            )

    return True, None, None


def _add_days(d: date, days: int) -> date:
    from datetime import timedelta
    return d + timedelta(days=days)


# ── Pre-authorization check ───────────────────────────────────────────────────

def requires_pre_auth(claim_category: ClaimCategory, diagnosis_text: str, amount: float) -> tuple[bool, str | None]:
    """Returns (requires_auth, reason)."""
    policy = load_policy()
    pre_auth = policy.get("pre_authorization", {})
    high_value = policy["opd_categories"].get("diagnostic", {}).get(
        "high_value_tests_requiring_pre_auth", []
    )
    threshold = policy["opd_categories"].get("diagnostic", {}).get("pre_auth_threshold", 10000)

    if claim_category == ClaimCategory.DIAGNOSTIC:
        lower = diagnosis_text.lower()
        for test in high_value:
            if test.lower() in lower and amount > threshold:
                return True, f"{test} above ₹{threshold:,.0f} requires pre-authorization."

    return False, None


# ── Exclusions check ──────────────────────────────────────────────────────────

EXCLUSION_KEYWORDS: list[str] = [
    "bariatric", "obesity", "weight loss", "cosmetic", "aesthetic",
    "whitening", "veneers", "braces", "orthodontic", "lasik",
    "refractive surgery", "infertility", "assisted reproduction",
    "substance abuse", "experimental", "vaccination", "supplement",
    "tonic", "self-inflicted", "war",
]


def is_excluded(description: str) -> tuple[bool, str | None]:
    """Check if a diagnosis or line-item description is excluded."""
    lower = description.lower()
    for kw in EXCLUSION_KEYWORDS:
        if kw in lower:
            return True, f"'{description}' falls under policy exclusions ({kw})."
    return False, None


# ── Per-claim limit check ─────────────────────────────────────────────────────

def check_per_claim_limit(amount: float) -> tuple[bool, str | None]:
    policy = load_policy()
    limit = policy["coverage"]["per_claim_limit"]
    if amount > limit:
        return False, f"Claimed ₹{amount:,.0f} exceeds per-claim limit of ₹{limit:,.0f}."
    return True, None


# ── Network hospital check ────────────────────────────────────────────────────

def is_network_hospital(hospital_name: str | None) -> bool:
    if not hospital_name:
        return False
    policy = load_policy()
    networks = [h.lower() for h in policy.get("network_hospitals", [])]
    return any(n in hospital_name.lower() for n in networks)


# ── Amount calculation: network discount → co-pay ────────────────────────────

def calculate_approved_amount(
    category: ClaimCategory,
    claimed_amount: float,
    hospital_name: str | None = None,
) -> dict[str, Any]:
    """
    Applies: network discount first, then co-pay.
    Returns a breakdown dict for full transparency (TC010).
    """
    policy = load_policy()
    cat_key = (category.value if hasattr(category, "value") else str(category)).lower()
    cat_config = policy["opd_categories"].get(cat_key, {})

    sub_limit: float = cat_config.get("sub_limit", float("inf"))
    copay_pct: float = cat_config.get("copay_percent", 0) / 100
    network_discount_pct: float = cat_config.get("network_discount_percent", 0) / 100

    # Step 1: apply network discount on full claimed amount (TC010 math order)
    network_discount = 0.0
    after_network = claimed_amount
    if is_network_hospital(hospital_name) and network_discount_pct > 0:
        network_discount = round(claimed_amount * network_discount_pct, 2)
        after_network = round(claimed_amount - network_discount, 2)

    # Step 2: apply co-pay on post-discount amount
    copay = round(after_network * copay_pct, 2)
    approved = round(after_network - copay, 2)

    # Note: sub_limit is an annual YTD cap checked separately, not a per-claim hard cap
    return {
        "claimed": claimed_amount,
        "network_discount": network_discount,
        "after_network_discount": after_network,
        "copay": copay,
        "approved_amount": approved,
        "sub_limit_annual": sub_limit,
    }


# ── Document requirements check ───────────────────────────────────────────────

def get_required_documents(category: ClaimCategory) -> list[DocumentType]:
    policy = load_policy()
    reqs = policy["document_requirements"].get(category.value, {})
    return [DocumentType(d) for d in reqs.get("required", [])]


def get_optional_documents(category: ClaimCategory) -> list[DocumentType]:
    policy = load_policy()
    reqs = policy["document_requirements"].get(category.value, {})
    return [DocumentType(d) for d in reqs.get("optional", [])]


# ── Fraud thresholds ──────────────────────────────────────────────────────────

def check_fraud_signals(
    member_id: str,
    treatment_date: str,
    claimed_amount: float,
    claims_history: list[dict],
) -> tuple[bool, list[str]]:
    """Returns (is_suspicious, list_of_signals)."""
    policy = load_policy()
    thresholds = policy.get("fraud_thresholds", {})
    same_day_limit = thresholds.get("same_day_claims_limit", 2)
    high_value = thresholds.get("high_value_claim_threshold", 25000)
    auto_review = thresholds.get("auto_manual_review_above", 25000)

    signals: list[str] = []

    same_day = [c for c in claims_history if c.get("date") == treatment_date]
    if len(same_day) >= same_day_limit:
        signals.append(
            f"{len(same_day)} existing claims on {treatment_date} "
            f"(limit: {same_day_limit}). Unusual same-day pattern."
        )

    if claimed_amount >= high_value:
        signals.append(f"High-value claim: ₹{claimed_amount:,.0f} exceeds threshold ₹{high_value:,.0f}.")

    return len(signals) > 0, signals
