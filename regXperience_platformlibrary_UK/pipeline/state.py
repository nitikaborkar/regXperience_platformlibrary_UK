"""
Shared state object that flows through the LangGraph graph.
All nodes read from and write to this typed dictionary.
"""

from __future__ import annotations
from typing import Any, Optional, TypedDict


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

class Chunk(TypedDict):
    chunk_id: str
    chunk_index: int
    text: str
    byte_offset_start: int
    byte_offset_end: int
    page_estimate: Optional[int]
    section_heading: Optional[str]


class ExtractedRequirement(TypedDict):
    requirement_text: str
    source_verbatim: Optional[str]       # original-language verbatim text
    clause_reference: Optional[str]
    bnm_tag: Optional[str]               # S=Shall/Must | E=Expects | G=Should | R=Recommended
    sub_domain: Optional[str]
    requirement_category: Optional[str]
    keywords: list[str]
    applies_to: list[str]
    source_chunk_id: str
    page_estimate: Optional[int]


class VerifiedRequirement(ExtractedRequirement):
    req_id: str
    doc_id: str
    jurisdiction: str
    domain: str
    legal_force: str
    verified: bool
    similarity_score: float
    verification_note: Optional[str]
    verbatim_present: bool
    extracted_at: str


# ---------------------------------------------------------------------------
# Document Registry Entry
# ---------------------------------------------------------------------------

class DocumentRegistryEntry(TypedDict):
    doc_id: str
    file_path: str
    source_url: Optional[str]
    jurisdiction: str
    issuer: str
    document_title: str
    instrument_type: str
    domain: str
    legal_force: str
    effective_date: Optional[str]
    applicable_entities: list[str]
    legal_basis: list[str]
    has_sg_clause_tags: bool
    mas_notice_number: Optional[str]
    is_cross_sector: bool
    chunk_strategy: str                  # "clause" | "fixed" | "mixed"
    total_pages: Optional[int]
    total_chunks: int
    processed_at: str
    # ── internal only — stripped before writing to disk ───────────────────────
    raw_text: str
    file_hash: str
    run_id: str
    flagged_for_review: bool
    instrument_type_confidence: float


# ---------------------------------------------------------------------------
# Top-level pipeline state
# ---------------------------------------------------------------------------

class PipelineState(TypedDict):
    # ── inputs ────────────────────────────────────────────────────────────────
    source_url: Optional[str]
    raw_input_path: str
    title: str
    source_authority: str

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    document: Optional[DocumentRegistryEntry]

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    chunks: list[Chunk]
    extracted_requirements: list[ExtractedRequirement]
    verified_requirements: list[VerifiedRequirement]
    human_review_queue: list[dict[str, Any]]

    # ── pipeline metadata ─────────────────────────────────────────────────────
    errors: list[str]
    pipeline_complete: bool