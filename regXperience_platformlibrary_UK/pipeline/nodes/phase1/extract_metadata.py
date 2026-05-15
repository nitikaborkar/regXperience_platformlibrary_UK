"""
Node 1.3 — Extract Metadata
LLM call: extract jurisdiction, issuing authority, regulation name,
version/year, regulatory domain, applicable entities, legal force
language, and document structure signals.
"""

from __future__ import annotations

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import PipelineState

_EXCERPT_CHARS = 2000 * 4


def extract_metadata(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])
    raw_text = doc["raw_text"]
    excerpt = raw_text[:_EXCERPT_CHARS]

    system_prompt = render_prompt("metadata_extraction_system")
    user_prompt = render_prompt(
        "metadata_extraction_user",
        title=doc.get("regulation_name") or state.get("title", "(unknown)"),
        source_authority=doc.get("issuing_authority") or state.get("source_authority", ""),
        source_url=doc.get("source_url", ""),
        document_excerpt=excerpt,
    )

    result: dict = call_llm_json(system_prompt, user_prompt)

    # Map LLM output onto document registry entry fields
    _update_field(doc, result, "jurisdiction")
    _update_field(doc, result, "issuing_authority")
    _update_field(doc, result, "regulation_name")
    _update_field(doc, result, "instrument_code")
    _update_field(doc, result, "year_issued", cast=int)
    _update_field(doc, result, "regulatory_domain")
    _update_field(doc, result, "topic_category")
    _update_field(doc, result, "applies_to")
    _update_field(doc, result, "legal_force")
    _update_field(doc, result, "compliance_tier")
    _update_field(doc, result, "structure_type")
    _update_field(doc, result, "has_annexures", cast=bool)
    _update_field(doc, result, "companion_docs")
    _update_field(doc, result, "reporting_standards")

    print(
        f"[Metadata] jurisdiction={doc.get('jurisdiction')!r} | "
        f"authority={doc.get('issuing_authority')!r} | "
        f"domain={doc.get('regulatory_domain')!r} | "
        f"legal_force={doc.get('legal_force')!r}"
    )

    return {**state, "document": doc}


def _update_field(doc: dict, result: dict, key: str, cast=None) -> None:
    if key in result and result[key] is not None:
        val = result[key]
        if cast is not None:
            try:
                val = cast(val)
            except (TypeError, ValueError):
                pass
        doc[key] = val
