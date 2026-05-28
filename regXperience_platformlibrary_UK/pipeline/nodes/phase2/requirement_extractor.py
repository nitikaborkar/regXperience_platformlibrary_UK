"""
Node 2.2 — Requirement Extractor
LLM call (per chunk): extract all regulatory requirements.
Returns structured JSON per the new schema.
"""

from __future__ import annotations
from typing import Any

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import ExtractedRequirement, PipelineState


def requirement_extractor(state: PipelineState) -> PipelineState:
    doc = state["document"]
    chunks = state["chunks"]
    total = len(chunks)

    all_requirements: list[ExtractedRequirement] = []
    applies_to_str = ", ".join(doc.get("applicable_entities", [])) or "not specified"

    for chunk in chunks:
        system_prompt = render_prompt("requirement_extraction_system")
        user_prompt = render_prompt(
            "requirement_extraction_user",
            document_title=doc.get("document_title", ""),
            issuer=doc.get("issuer", ""),
            instrument_type=doc.get("instrument_type", ""),
            legal_force=doc.get("legal_force", ""),
            jurisdiction=doc.get("jurisdiction", ""),
            domain=doc.get("domain", ""),
            applies_to=applies_to_str,
            chunk_index=str(chunk["chunk_index"] + 1),
            total_chunks=str(total),
            section_heading=chunk.get("section_heading") or "N/A",
            page_estimate=str(chunk.get("page_estimate") or "unknown"),
            chunk_text=chunk["text"],
        )

        try:
            result: Any = call_llm_json(system_prompt, user_prompt)
        except Exception as exc:
            print(f"  [Extractor] ⚠  Chunk {chunk['chunk_index']+1}/{total} failed: {exc}")
            continue

        if isinstance(result, dict):
            result = result.get("requirements", [])
        if not isinstance(result, list):
            result = []

        for item in result:
            req = ExtractedRequirement(
                requirement_text=item.get("requirement_text", ""),
                source_verbatim=item.get("source_verbatim"),
                clause_reference=item.get("clause_reference"),
                bnm_tag=item.get("bnm_tag"),
                sub_domain=item.get("sub_domain"),
                requirement_category=item.get("requirement_category"),
                keywords=item.get("keywords", []),
                applies_to=item.get("applies_to", []),
                source_chunk_id=chunk["chunk_id"],
                page_estimate=chunk.get("page_estimate"),
            )
            if req["requirement_text"].strip():
                all_requirements.append(req)

        print(
            f"  [Extractor] Chunk {chunk['chunk_index']+1}/{total} → "
            f"{len(result)} requirement(s) found"
        )

    print(f"[Extractor] Total raw requirements: {len(all_requirements)}")
    return {**state, "extracted_requirements": all_requirements}