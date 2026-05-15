"""
Node 1.2 — Classify Document Type
LLM call: classify document type and output confidence score.
If confidence < 0.75, flag for human review and block Phase 2.
"""

from __future__ import annotations

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import PipelineState

_CONFIDENCE_THRESHOLD = 0.75

# Tokenise cheaply — 1 token ≈ 4 chars
_EXCERPT_CHARS = 2000 * 4


def classify_document_type(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])
    raw_text = doc["raw_text"]
    excerpt = raw_text[:_EXCERPT_CHARS]

    system_prompt = render_prompt("classify_system")
    user_prompt = render_prompt(
        "classify_user",
        title=doc.get("regulation_name") or state.get("title", "(unknown)"),
        source_authority=doc.get("issuing_authority") or state.get("source_authority", ""),
        source_url=doc.get("source_url", ""),
        document_excerpt=excerpt,
    )

    result: dict = call_llm_json(system_prompt, user_prompt)

    doc["document_type"] = result.get("document_type", "")
    doc["document_type_confidence"] = float(result.get("document_type_confidence", 0.0))

    flagged = doc["document_type_confidence"] < _CONFIDENCE_THRESHOLD
    doc["flagged_for_review"] = flagged

    if flagged:
        print(
            f"[Classify] ⚠  Low confidence ({doc['document_type_confidence']:.2f}) "
            f"for document_type={doc['document_type']!r} — flagged for human review"
        )
    else:
        print(
            f"[Classify] document_type={doc['document_type']!r} "
            f"(confidence={doc['document_type_confidence']:.2f})"
        )

    errors = list(state.get("errors", []))
    if flagged:
        errors.append(
            f"Document type confidence {doc['document_type_confidence']:.2f} < "
            f"{_CONFIDENCE_THRESHOLD} — human review required before Phase 2."
        )

    return {**state, "document": doc, "errors": errors}
