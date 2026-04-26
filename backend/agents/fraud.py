"""
Agent 4 — Fraud Detector

Checks claim patterns against fraud thresholds from policy_terms.json.
Routes suspicious claims to MANUAL_REVIEW — never auto-rejects.

Covers TC009: multiple same-day claims from same member.

Input:  ClaimSubmission + ParsedClaim
Output: FraudResult + TraceStep
"""
from __future__ import annotations
from dataclasses import dataclass, field

from agents.parser import ParsedClaim
from core.models import ClaimSubmission, TraceStep, AgentStatus
from core import policy_engine as pe


@dataclass
class FraudResult:
    is_suspicious: bool = False
    signals: list[str] = field(default_factory=list)
    confidence_delta: float = 0.0


def run_fraud_detector(
    submission: ClaimSubmission,
    parsed: ParsedClaim,
    simulate_failure: bool = False,
) -> tuple[FraudResult, TraceStep]:

    if simulate_failure:
        return _simulate_failure()

    result = FraudResult()

    # Convert ClaimsHistory objects to dicts for policy engine
    history_dicts = [
        {"date": h.date, "amount": h.amount, "provider": h.provider}
        for h in submission.claims_history
    ]

    is_suspicious, signals = pe.check_fraud_signals(
        submission.member_id,
        submission.treatment_date,
        submission.claimed_amount,
        history_dicts,
    )

    result.is_suspicious = is_suspicious
    result.signals = signals

    if is_suspicious:
        result.confidence_delta = -0.2

    status = AgentStatus.FAILED if is_suspicious else AgentStatus.SUCCESS
    detail = (
        f"Fraud signals detected: {' | '.join(signals)}"
        if is_suspicious
        else f"No fraud signals. Same-day claims: {len(history_dicts)}. Amount: ₹{submission.claimed_amount}."
    )

    trace = TraceStep(
        agent="fraud_detector",
        status=status,
        detail=detail,
        confidence_delta=result.confidence_delta,
        data={
            "is_suspicious": is_suspicious,
            "signals": signals,
            "claims_history_count": len(history_dicts),
        },
    )

    return result, trace


def _simulate_failure() -> tuple[FraudResult, TraceStep]:
    result = FraudResult()
    result.confidence_delta = -0.1
    trace = TraceStep(
        agent="fraud_detector",
        status=AgentStatus.FAILED,
        detail="Fraud detector failed — component error simulated. Skipped.",
        confidence_delta=-0.1,
        data={"simulated_failure": True},
    )
    return result, trace
