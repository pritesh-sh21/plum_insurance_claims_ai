"""
Agent 3 — Policy Evaluator

Takes parsed claim data from Agent 2 and runs every policy check.
Uses only pure functions from policy_engine.py — no LLM calls here.

Checks (in order):
  1. Member validity
  2. Waiting period
  3. Pre-authorization
  4. Per-claim limit
  5. Exclusions (full claim + line-item level for TC006)
  6. Amount calculation (network discount → copay)

Input:  ParsedClaim + ClaimSubmission
Output: EvaluationResult + TraceStep
"""
from __future__ import annotations
from dataclasses import dataclass, field

from agents.parser import ParsedClaim
from core.models import (
    ClaimSubmission, RejectionReason, TraceStep, AgentStatus,
    LineItemDecision,
)
from core import policy_engine as pe


@dataclass
class EvaluationResult:
    passed: bool = True
    rejection_reasons: list[RejectionReason] = field(default_factory=list)
    rejection_messages: list[str] = field(default_factory=list)
    approved_amount: float = 0.0
    line_item_decisions: list[LineItemDecision] = field(default_factory=list)
    calculation_breakdown: dict = field(default_factory=dict)
    confidence_delta: float = 0.0
    checks_run: list[str] = field(default_factory=list)
    manual_review: bool = False


def run_policy_evaluator(
    submission: ClaimSubmission,
    parsed: ParsedClaim,
    simulate_failure: bool = False,
) -> tuple[EvaluationResult, TraceStep]:

    if simulate_failure:
        return _simulate_failure()

    result = EvaluationResult()
    diagnosis = parsed.diagnosis or _infer_diagnosis(submission, parsed)
    # Combine diagnosis + tests ordered for pre-auth and exclusion checks (TC007)
    full_text = " ".join(filter(None, [
        diagnosis,
        " ".join(parsed.tests_ordered or []),
        parsed.treatment or "",
    ]))

    # ── Check 1: Member exists ────────────────────────────────────────────────
    member = pe.get_member(submission.member_id)
    if not member:
        result.passed = False
        result.rejection_reasons.append(RejectionReason.DOCUMENT_MISMATCH)
        result.rejection_messages.append(f"Member {submission.member_id} not found in policy.")
        result.checks_run.append("member_lookup: FAILED")
        return result, _build_trace(result)
    result.checks_run.append(f"member_lookup: PASS ({member['name']})")

    # ── Check 2: Waiting period ───────────────────────────────────────────────
    eligible, wait_msg, eligible_from = pe.check_waiting_period(
        submission.member_id,
        submission.treatment_date,
        diagnosis or "",
    )
    if not eligible:
        result.passed = False
        result.rejection_reasons.append(RejectionReason.WAITING_PERIOD)
        result.rejection_messages.append(wait_msg)
        result.checks_run.append(f"waiting_period: FAILED — {wait_msg}")
    else:
        result.checks_run.append("waiting_period: PASS")

    # ── Check 3: Pre-authorization ────────────────────────────────────────────
    needs_auth, auth_msg = pe.requires_pre_auth(
        submission.claim_category,
        full_text or "",
        submission.claimed_amount,
    )
    if needs_auth:
        result.passed = False
        result.rejection_reasons.append(RejectionReason.PRE_AUTH_MISSING)
        result.rejection_messages.append(
            auth_msg + " To resubmit: obtain pre-authorization from your insurer, "
            "then resubmit with the pre-auth reference number."
        )
        result.checks_run.append(f"pre_auth: FAILED — {auth_msg}")
    else:
        result.checks_run.append("pre_auth: PASS (not required)")

    # ── Check 4: Per-claim limit ──────────────────────────────────────────────
    # DENTAL and VISION have their own category sub-limits (₹10K and ₹5K).
    # The general coverage.per_claim_limit (₹5K) is an OPD guard for
    # consultation/pharmacy — it does not apply to itemized dental/vision claims.
    from core.models import ClaimCategory as CC
    skip_per_claim = submission.claim_category in {CC.DENTAL, CC.VISION}

    if skip_per_claim:
        result.checks_run.append(
            f"per_claim_limit: SKIPPED for {submission.claim_category.value} "
            f"(category sub-limit applies instead)"
        )
    else:
        within_limit, limit_msg = pe.check_per_claim_limit(submission.claimed_amount)
        if not within_limit:
            result.passed = False
            result.rejection_reasons.append(RejectionReason.PER_CLAIM_EXCEEDED)
            result.rejection_messages.append(limit_msg)
            result.checks_run.append(f"per_claim_limit: FAILED — {limit_msg}")
        else:
            result.checks_run.append(
                f"per_claim_limit: PASS (₹{submission.claimed_amount} within limit)"
            )

    # ── Check 5: Exclusions — full claim level ────────────────────────────────
    excl, excl_msg = pe.is_excluded(full_text or "")
    if excl:
        result.passed = False
        result.rejection_reasons.append(RejectionReason.EXCLUDED_CONDITION)
        result.rejection_messages.append(excl_msg)
        result.checks_run.append(f"exclusions: FAILED — {excl_msg}")
    else:
        result.checks_run.append("exclusions: PASS")

    # ── Check 5b: Line-item exclusions (TC006 dental partial) ─────────────────
    line_items = parsed.line_items or _extract_line_items(submission)
    if line_items:
        result.line_item_decisions = _evaluate_line_items(line_items)
        approved_items = [li for li in result.line_item_decisions if li.approved_amount > 0]
        rejected_items = [li for li in result.line_item_decisions if li.approved_amount == 0]
        if rejected_items:
            result.checks_run.append(
                f"line_item_exclusions: {len(rejected_items)} item(s) excluded — "
                + ", ".join(li.description for li in rejected_items)
            )
        else:
            result.checks_run.append("line_item_exclusions: all items covered")

    # ── Check 6: Calculate approved amount ────────────────────────────────────
    if result.passed or (result.line_item_decisions and any(
        li.approved_amount > 0 for li in result.line_item_decisions
    )):
        if result.line_item_decisions:
            # Use sum of approved line items as the base
            approved_base = sum(li.approved_amount for li in result.line_item_decisions)
            breakdown = pe.calculate_approved_amount(
                submission.claim_category,
                approved_base,
                submission.hospital_name,
            )
        else:
            breakdown = pe.calculate_approved_amount(
                submission.claim_category,
                submission.claimed_amount,
                submission.hospital_name,
            )
        result.approved_amount = breakdown["approved_amount"]
        result.calculation_breakdown = breakdown
        result.checks_run.append(
            f"amount_calc: ₹{submission.claimed_amount} → "
            f"network_discount=₹{breakdown['network_discount']} → "
            f"copay=₹{breakdown['copay']} → "
            f"approved=₹{result.approved_amount}"
        )

    return result, _build_trace(result)


# ── Line item evaluator (TC006) ───────────────────────────────────────────────

def _evaluate_line_items(line_items: list[dict]) -> list[LineItemDecision]:
    decisions = []
    for item in line_items:
        desc = item.get("description", "")
        amount = float(item.get("amount", 0))
        excluded, excl_msg = pe.is_excluded(desc)
        decisions.append(LineItemDecision(
            description=desc,
            claimed_amount=amount,
            approved_amount=0.0 if excluded else amount,
            reason=excl_msg if excluded else "Covered under policy",
        ))
    return decisions


# ── Helpers ───────────────────────────────────────────────────────────────────

def _infer_diagnosis(submission: ClaimSubmission, parsed: ParsedClaim) -> str:
    """Pull diagnosis from any available source."""
    if parsed.diagnosis:
        return parsed.diagnosis
    if parsed.treatment:
        return parsed.treatment
    for doc in submission.documents:
        if doc.content:
            d = doc.content.get("diagnosis") or doc.content.get("treatment")
            if d:
                return d
    return ""


def _extract_line_items(submission: ClaimSubmission) -> list[dict]:
    """Pull line items directly from submission documents if parser didn't find them."""
    for doc in submission.documents:
        if doc.content and doc.content.get("line_items"):
            return doc.content["line_items"]
    return []


def _simulate_failure() -> tuple[EvaluationResult, TraceStep]:
    result = EvaluationResult()
    result.passed = True
    result.confidence_delta = -0.3
    result.checks_run = ["policy_evaluation: SKIPPED — component failure"]
    trace = TraceStep(
        agent="policy_evaluator",
        status=AgentStatus.FAILED,
        detail="Policy evaluator failed — component error simulated. Skipped. Manual review recommended.",
        confidence_delta=-0.3,
        data={"simulated_failure": True},
    )
    return result, trace


def _build_trace(result: EvaluationResult) -> TraceStep:
    status = AgentStatus.SUCCESS if result.passed else AgentStatus.FAILED
    checks_summary = " | ".join(result.checks_run)
    return TraceStep(
        agent="policy_evaluator",
        status=status,
        detail=checks_summary,
        confidence_delta=result.confidence_delta,
        data={
            "passed": result.passed,
            "rejection_reasons": [r.value for r in result.rejection_reasons],
            "approved_amount": result.approved_amount,
            "checks_run": result.checks_run,
        },
    )
