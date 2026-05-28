"""
Node 1.2 — Classify Instrument Type
LLM call: classify instrument type with confidence score.
If confidence < 0.75, flag for human review and block Phase 2.
"""

from __future__ import annotations

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import PipelineState

_CONFIDENCE_THRESHOLD = 0.75
_EXCERPT_CHARS = 2000 * 4


def classify_document_type(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])
    excerpt = doc["raw_text"][:_EXCERPT_CHARS]

    system_prompt = render_prompt("classify_system")
    user_prompt = render_prompt(
        "classify_user",
        title=doc.get("document_title") or state.get("title", "(unknown)"),
        source_authority=doc.get("issuer") or state.get("source_authority", ""),
        source_url=doc.get("source_url") or doc.get("file_path", ""),
        document_excerpt=excerpt,
    )

    result: dict = call_llm_json(system_prompt, user_prompt)

    doc["instrument_type"] = result.get("instrument_type", "")
    doc["instrument_type_confidence"] = float(result.get("instrument_type_confidence", 0.0))

    flagged = doc["instrument_type_confidence"] < _CONFIDENCE_THRESHOLD
    doc["flagged_for_review"] = flagged

    errors = list(state.get("errors", []))
    if flagged:
        print(
            f"[Classify] ⚠  Low confidence ({doc['instrument_type_confidence']:.2f}) "
            f"for instrument_type={doc['instrument_type']!r} — flagged for human review"
        )
        errors.append(
            f"Instrument type confidence {doc['instrument_type_confidence']:.2f} < "
            f"{_CONFIDENCE_THRESHOLD} — human review required before Phase 2."
        )
    else:
        print(
            f"[Classify] instrument_type={doc['instrument_type']!r} "
            f"(confidence={doc['instrument_type_confidence']:.2f})"
        )

    return {**state, "document": doc, "errors": errors}