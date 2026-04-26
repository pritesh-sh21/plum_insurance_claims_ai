"""
Agent 5 — Decision Synthesizer

Collects outputs from Agents 2, 3, 4 and produces the final ClaimDecision.
Determines APPROVED / PARTIAL / REJECTED / MANUAL_REVIEW.
Sets final confidence score — drops further if any upstream agent degraded.

Input:  All previous agent results
Output: ClaimDecision
"""
from __future__ import annotations
import uuid

from agents.parser import ParsedClaim
from agents.evaluator import EvaluationResult
from agents.fraud import FraudResult
from core.models import (
    ClaimSubmission, ClaimDecision, DecisionType,
    TraceStep, AgentStatus,
)


def run_decision_synthesizer(
    submission: ClaimSubmission,
    parsed: ParsedClaim,
    evaluation: EvaluationResult,
    fraud: FraudResult,
    all_traces: list[TraceStep],
    component_failures: list[str],
) -> ClaimDecision:

    claim_id = str(uuid.uuid4())[:8].upper()

    # ── Base confidence starts at 1.0, reduced by each agent ─────────────────
    confidence = 1.0
    # For clear-cut hard policy rejections (exclusion, waiting period, per-claim)
    # parser quality doesn't affect confidence — the policy rule is certain
    from core.models import RejectionReason as RR
    hard_policy_rejection = any(r in [RR.EXCLUDED_CONDITION, RR.WAITING_PERIOD,
                                       RR.PRE_AUTH_MISSING, RR.PER_CLAIM_EXCEEDED]
                                 for r in evaluation.rejection_reasons)
    if not hard_policy_rejection:
        confidence += parsed.overall_confidence - 1.0      # parser quality matters
    confidence += sum(t.confidence_delta for t in all_traces)  # agent deltas

    # Extra reduction for component failures
    confidence -= len(component_failures) * 0.15
    confidence = round(max(0.1, min(1.0, confidence)), 2)

    # ── Determine decision ────────────────────────────────────────────────────

    # Fraud always routes to MANUAL_REVIEW
    if fraud.is_suspicious:
        return _make_decision(
            claim_id, submission, all_traces, component_failures,
            decision=DecisionType.MANUAL_REVIEW,
            approved_amount=0.0,
            confidence=confidence,
            message=(
                "Claim flagged for manual review due to unusual patterns: "
                + " | ".join(fraud.signals)
            ),
            rejection_reasons=[],
            line_item_decisions=evaluation.line_item_decisions,
            breakdown=evaluation.calculation_breakdown,
            manual_review=True,
        )

    # Hard rejection — policy checks failed at claim level (overrides line items)
    if not evaluation.passed:
        return _make_decision(
            claim_id, submission, all_traces, component_failures,
            decision=DecisionType.REJECTED,
            approved_amount=0.0,
            confidence=confidence,
            message=" | ".join(evaluation.rejection_messages),
            rejection_reasons=evaluation.rejection_reasons,
            line_item_decisions=[],
            breakdown={},
            manual_review=len(component_failures) > 0,
        )

    # Partial — some line items approved, some rejected (TC006)
    if evaluation.line_item_decisions:
        approved_items = [li for li in evaluation.line_item_decisions if li.approved_amount > 0]
        rejected_items = [li for li in evaluation.line_item_decisions if li.approved_amount == 0]

        if approved_items and rejected_items:
            approved_total = sum(li.approved_amount for li in approved_items)
            rejected_descs = [f"{li.description} (₹{li.claimed_amount:.0f}): {li.reason}"
                              for li in rejected_items]
            approved_descs = [f"{li.description} (₹{li.approved_amount:.0f}): covered"
                              for li in approved_items]
            return _make_decision(
                claim_id, submission, all_traces, component_failures,
                decision=DecisionType.PARTIAL,
                approved_amount=evaluation.approved_amount,
                confidence=confidence,
                message=(
                    f"Partially approved ₹{evaluation.approved_amount:.0f} of ₹{submission.claimed_amount:.0f}. "
                    f"Approved: {'; '.join(approved_descs)}. "
                    f"Rejected: {'; '.join(rejected_descs)}."
                ),
                rejection_reasons=evaluation.rejection_reasons,
                line_item_decisions=evaluation.line_item_decisions,
                breakdown=evaluation.calculation_breakdown,
                manual_review=len(component_failures) > 0,
            )

        elif not approved_items:
            # All line items excluded
            return _make_decision(
                claim_id, submission, all_traces, component_failures,
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                confidence=confidence,
                message="All line items excluded under policy.",
                rejection_reasons=evaluation.rejection_reasons,
                line_item_decisions=evaluation.line_item_decisions,
                breakdown={},
                manual_review=len(component_failures) > 0,
            )

    # Full approval
    breakdown_note = ""
    if evaluation.calculation_breakdown:
        b = evaluation.calculation_breakdown
        parts = []
        if b.get("network_discount", 0) > 0:
            parts.append(f"network discount ₹{b['network_discount']:.0f}")
        if b.get("copay", 0) > 0:
            parts.append(f"co-pay ₹{b['copay']:.0f}")
        if parts:
            breakdown_note = f" ({', '.join(parts)} deducted)"

    manual = len(component_failures) > 0
    return _make_decision(
        claim_id, submission, all_traces, component_failures,
        decision=DecisionType.APPROVED,
        approved_amount=evaluation.approved_amount,
        confidence=confidence,
        message=(
            f"Claim approved for ₹{evaluation.approved_amount:.0f}{breakdown_note}."
            + (" Manual review recommended due to incomplete processing." if manual else "")
        ),
        rejection_reasons=[],
        line_item_decisions=evaluation.line_item_decisions,
        breakdown=evaluation.calculation_breakdown,
        manual_review=manual,
    )


# ── Builder ───────────────────────────────────────────────────────────────────

def _make_decision(
    claim_id: str,
    submission: ClaimSubmission,
    all_traces: list[TraceStep],
    component_failures: list[str],
    decision: DecisionType,
    approved_amount: float,
    confidence: float,
    message: str,
    rejection_reasons: list,
    line_item_decisions: list,
    breakdown: dict,
    manual_review: bool,
) -> ClaimDecision:

    # Final synthesizer trace
    synth_trace = TraceStep(
        agent="decision_synthesizer",
        status=AgentStatus.SUCCESS,
        detail=(
            f"Decision: {decision.value}. "
            f"Approved: ₹{approved_amount:.0f}. "
            f"Confidence: {confidence}. "
            f"Component failures: {component_failures or 'none'}."
        ),
        confidence_delta=0.0,
        data={"decision": decision.value, "approved_amount": approved_amount},
    )

    return ClaimDecision(
        claim_id=claim_id,
        member_id=submission.member_id,
        decision=decision,
        approved_amount=approved_amount,
        claimed_amount=submission.claimed_amount,
        rejection_reasons=rejection_reasons,
        line_item_decisions=line_item_decisions,
        confidence_score=confidence,
        message=message,
        trace=all_traces + [synth_trace],
        component_failures=component_failures,
        manual_review_recommended=manual_review,
        calculation_breakdown=breakdown or None,
    )
