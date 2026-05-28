"""
Node 2.5 — Review Gate
Routes requirements:
  - verified=False OR similarity_score < 0.80 → human_review_queue
  - otherwise → pass to write_requirements
"""

from __future__ import annotations

from pipeline.state import PipelineState

_SCORE_THRESHOLD = 0.80


def review_gate(state: PipelineState) -> PipelineState:
    verified = state["verified_requirements"]
    human_review = list(state.get("human_review_queue", []))

    passed: list = []
    flagged: list = []

    for req in verified:
        if not req["verified"] or req["similarity_score"] < _SCORE_THRESHOLD:
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
        return f"verified=False (score={req['similarity_score']:.2f})"
    return f"Low similarity score ({req['similarity_score']:.2f} < {_SCORE_THRESHOLD})"