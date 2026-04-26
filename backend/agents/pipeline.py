"""
LangGraph Pipeline — wires all 5 agents into a graph.

Flow:
  verifier → parser → evaluator → fraud_detector → synthesizer

Graceful degradation (TC011):
  If any node raises an exception, the pipeline catches it, records the
  failure, reduces confidence, and continues to the next node.
  The system never crashes — it always produces a ClaimDecision.

State is passed between nodes via ClaimState TypedDict.
"""
from __future__ import annotations
from typing import TypedDict, Any

from langgraph.graph import StateGraph, END

from core.models import (
    ClaimSubmission, ClaimDecision, DecisionType,
    TraceStep, AgentStatus,
)
from agents.verifier import run_document_verifier
from agents.parser import run_document_parser, ParsedClaim
from agents.evaluator import run_policy_evaluator, EvaluationResult
from agents.fraud import run_fraud_detector, FraudResult
from agents.synthesizer import run_decision_synthesizer


# ── Graph state ───────────────────────────────────────────────────────────────

class ClaimState(TypedDict):
    submission: ClaimSubmission
    traces: list[TraceStep]
    component_failures: list[str]
    verification_errors: list[Any]
    parsed: Any           # ParsedClaim | None
    evaluation: Any       # EvaluationResult | None
    fraud: Any            # FraudResult | None
    final_decision: Any   # ClaimDecision | None
    stopped_early: bool


# ── Node 1: Document verifier ─────────────────────────────────────────────────

def node_verifier(state: ClaimState) -> ClaimState:
    try:
        errors, trace = run_document_verifier(state["submission"])
        state["traces"].append(trace)
        state["verification_errors"] = [e.model_dump() for e in errors]
        if errors:
            state["stopped_early"] = True
    except Exception as e:
        state["component_failures"].append(f"verifier: {str(e)}")
        state["traces"].append(TraceStep(
            agent="document_verifier",
            status=AgentStatus.FAILED,
            detail=f"Verifier crashed: {e}",
            confidence_delta=-0.2,
        ))
    return state


# ── Node 2: Document parser ───────────────────────────────────────────────────

def node_parser(state: ClaimState) -> ClaimState:
    simulate = state["submission"].simulate_component_failure
    try:
        parsed, trace = run_document_parser(
            state["submission"],
            simulate_failure=simulate,
        )
        state["parsed"] = parsed
        state["traces"].append(trace)
        if trace.status == AgentStatus.FAILED:
            state["component_failures"].append("document_parser")
    except Exception as e:
        state["component_failures"].append(f"parser: {str(e)}")
        state["parsed"] = _empty_parsed()
        state["traces"].append(TraceStep(
            agent="document_parser",
            status=AgentStatus.FAILED,
            detail=f"Parser crashed: {e}",
            confidence_delta=-0.4,
        ))
    return state


# ── Node 3: Policy evaluator ──────────────────────────────────────────────────

def node_evaluator(state: ClaimState) -> ClaimState:
    simulate = state["submission"].simulate_component_failure
    try:
        evaluation, trace = run_policy_evaluator(
            state["submission"],
            state["parsed"],
            simulate_failure=False,   # evaluator doesn't fail in TC011
        )
        state["evaluation"] = evaluation
        state["traces"].append(trace)
    except Exception as e:
        state["component_failures"].append(f"evaluator: {str(e)}")
        state["evaluation"] = _empty_evaluation()
        state["traces"].append(TraceStep(
            agent="policy_evaluator",
            status=AgentStatus.FAILED,
            detail=f"Evaluator crashed: {e}",
            confidence_delta=-0.3,
        ))
    return state


# ── Node 4: Fraud detector ────────────────────────────────────────────────────

def node_fraud(state: ClaimState) -> ClaimState:
    try:
        fraud, trace = run_fraud_detector(
            state["submission"],
            state["parsed"],
        )
        state["fraud"] = fraud
        state["traces"].append(trace)
    except Exception as e:
        state["component_failures"].append(f"fraud_detector: {str(e)}")
        state["fraud"] = _empty_fraud()
        state["traces"].append(TraceStep(
            agent="fraud_detector",
            status=AgentStatus.FAILED,
            detail=f"Fraud detector crashed: {e}",
            confidence_delta=-0.1,
        ))
    return state


# ── Node 5: Decision synthesizer ─────────────────────────────────────────────

def node_synthesizer(state: ClaimState) -> ClaimState:
    try:
        decision = run_decision_synthesizer(
            submission=state["submission"],
            parsed=state["parsed"],
            evaluation=state["evaluation"],
            fraud=state["fraud"],
            all_traces=state["traces"],
            component_failures=state["component_failures"],
        )
        state["final_decision"] = decision
    except Exception as e:
        state["component_failures"].append(f"synthesizer: {str(e)}")
        state["final_decision"] = _emergency_decision(state, str(e))
    return state


# ── Routing: stop early if doc verification failed ────────────────────────────

def should_continue(state: ClaimState) -> str:
    if state.get("stopped_early"):
        return "stopped"
    return "continue"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_pipeline() -> Any:
    graph = StateGraph(ClaimState)

    graph.add_node("verifier", node_verifier)
    graph.add_node("parser", node_parser)
    graph.add_node("evaluator", node_evaluator)
    graph.add_node("fraud", node_fraud)
    graph.add_node("synthesizer", node_synthesizer)

    graph.set_entry_point("verifier")

    # After verifier: if doc errors found, skip to END; else continue
    graph.add_conditional_edges(
        "verifier",
        should_continue,
        {"stopped": END, "continue": "parser"},
    )

    graph.add_edge("parser", "evaluator")
    graph.add_edge("evaluator", "fraud")
    graph.add_edge("fraud", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


# ── Main entry point ──────────────────────────────────────────────────────────

_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


def run_pipeline(submission: ClaimSubmission) -> dict:
    """
    Run the full claims pipeline.
    Always returns a dict — never raises.
    """
    pipeline = get_pipeline()

    initial_state: ClaimState = {
        "submission": submission,
        "traces": [],
        "component_failures": [],
        "verification_errors": [],
        "parsed": None,
        "evaluation": None,
        "fraud": None,
        "final_decision": None,
        "stopped_early": False,
    }

    final_state = pipeline.invoke(initial_state)

    # Stopped early — doc verification failed
    if final_state.get("stopped_early"):
        return {
            "status": "document_verification_failed",
            "errors": final_state["verification_errors"],
            "trace": [t.model_dump() for t in final_state["traces"]],
        }

    # Full decision produced
    decision: ClaimDecision = final_state["final_decision"]
    return {
        "status": "completed",
        "claim_id": decision.claim_id,
        "decision": decision.decision.value,
        "approved_amount": decision.approved_amount,
        "claimed_amount": decision.claimed_amount,
        "confidence_score": decision.confidence_score,
        "message": decision.message,
        "rejection_reasons": [r.value for r in decision.rejection_reasons],
        "line_item_decisions": [li.model_dump() for li in decision.line_item_decisions],
        "calculation_breakdown": decision.calculation_breakdown,
        "component_failures": decision.component_failures,
        "manual_review_recommended": decision.manual_review_recommended,
        "trace": [t.model_dump() for t in decision.trace],
    }


# ── Fallback empty states (graceful degradation) ──────────────────────────────

def _empty_parsed() -> ParsedClaim:
    p = ParsedClaim()
    p.overall_confidence = 0.3
    p.warnings = ["Parser unavailable — no extraction performed"]
    return p


def _empty_evaluation() -> EvaluationResult:
    e = EvaluationResult()
    e.passed = True   # give benefit of doubt when evaluator fails
    e.checks_run = ["policy_evaluation: SKIPPED — component failure"]
    e.confidence_delta = -0.3
    return e


def _empty_fraud() -> FraudResult:
    f = FraudResult()
    f.is_suspicious = False
    f.confidence_delta = 0.0
    return f


def _emergency_decision(state: ClaimState, error: str) -> ClaimDecision:
    """Last resort if synthesizer itself crashes."""
    import uuid
    from core.models import LineItemDecision
    return ClaimDecision(
        claim_id=str(uuid.uuid4())[:8].upper(),
        member_id=state["submission"].member_id,
        decision=DecisionType.MANUAL_REVIEW,
        approved_amount=0.0,
        claimed_amount=state["submission"].claimed_amount,
        confidence_score=0.1,
        message=f"System error — claim routed to manual review. Error: {error}",
        trace=state["traces"],
        component_failures=state["component_failures"] + [f"synthesizer: {error}"],
        manual_review_recommended=True,
    )
