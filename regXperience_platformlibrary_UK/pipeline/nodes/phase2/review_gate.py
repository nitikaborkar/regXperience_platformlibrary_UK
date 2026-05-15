"""
Node 2.5 — Review Gate
Decision node:
  - verified = false OR confidence < 0.80  → route to human_review queue
  - otherwise                              → pass to write_requirements
This node does NOT branch the graph itself; it partitions the
verified_requirements list so write_requirements only sees the good ones
and human_review_queue captures the rest.
The LangGraph conditional edge is defined in graph.py.
"""

from __future__ import annotations

from pipeline.state import PipelineState

_CONFIDENCE_THRESHOLD = 0.80


def review_gate(state: PipelineState) -> PipelineState:
    verified = state["verified_requirements"]
    human_review = list(state.get("human_review_queue", []))

    passed: list = []
    flagged: list = []

    for req in verified:
        if not req["verified"] or req["verification_confidence"] < _CONFIDENCE_THRESHOLD:
            flagged.append({**req, "review_reason": _reason(req)})
        else:
            passed.append(req)

    human_review.extend(flagged)

    print(
        f"[ReviewGate] {len(passed)} pass → output store | "
        f"{len(flagged)} flagged → human review queue"
    )

    return {
        **state,
        "verified_requirements": passed,
        "human_review_queue": human_review,
    }


def _reason(req: dict) -> str:
    if not req["verified"]:
        return f"verified=False (confidence={req['verification_confidence']:.2f})"
    return f"Low verification confidence ({req['verification_confidence']:.2f} < {_CONFIDENCE_THRESHOLD})"
