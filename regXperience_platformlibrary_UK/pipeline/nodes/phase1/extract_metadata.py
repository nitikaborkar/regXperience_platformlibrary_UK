"""
Node 1.3 — Extract Metadata
LLM call: extract jurisdiction, issuer, document title, instrument type,
effective date, applicable entities, legal basis, domain, legal force,
and jurisdiction-specific flags.
"""

from __future__ import annotations

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import PipelineState

_EXCERPT_CHARS = 2000 * 4


def extract_metadata(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])
    excerpt = doc["raw_text"][:_EXCERPT_CHARS]

    system_prompt = render_prompt("metadata_extraction_system")
    user_prompt = render_prompt(
        "metadata_extraction_user",
        title=doc.get("document_title") or state.get("title", "(unknown)"),
        source_authority=doc.get("issuer") or state.get("source_authority", ""),
        source_url=doc.get("source_url") or doc.get("file_path", ""),
        document_excerpt=excerpt,
    )

    result: dict = call_llm_json(system_prompt, user_prompt)

    _set(doc, result, "jurisdiction")
    _set(doc, result, "issuer")
    _set(doc, result, "document_title")
    _set(doc, result, "instrument_type")
    _set(doc, result, "domain")
    _set(doc, result, "legal_force")
    _set(doc, result, "effective_date")
    _set(doc, result, "applicable_entities")
    _set(doc, result, "legal_basis")
    _set(doc, result, "has_sg_clause_tags", cast=bool)
    _set(doc, result, "mas_notice_number")
    _set(doc, result, "is_cross_sector", cast=bool)

    print(
        f"[Metadata] jurisdiction={doc.get('jurisdiction')!r} | "
        f"issuer={doc.get('issuer')!r} | "
        f"domain={doc.get('domain')!r} | "
        f"legal_force={doc.get('legal_force')!r}"
    )

    return {**state, "document": doc}


def _set(doc: dict, result: dict, key: str, cast=None) -> None:
    if key in result and result[key] is not None:
        val = result[key]
        if cast is not None:
            try:
                val = cast(val)
            except (TypeError, ValueError):
                pass
        doc[key] = val