"""
Shared state object that flows through the LangGraph graph.
All nodes read from and write to this typed dictionary.
"""

from __future__ import annotations
from typing import Any, Optional, TypedDict


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

class ChunkStrategy(TypedDict):
    chunk_size_tokens: int
    overlap_tokens: int
    total_chunks: int


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
    section_reference: Optional[str]
    obligation_type: str          # Mandatory | Guidance | BestPractice
    obligation_language: str
    nature: list[str]
    actor: list[str]
    source_chunk_id: str
    page_estimate: Optional[int]


class VerifiedRequirement(ExtractedRequirement):
    requirement_id: str
    document_id: str
    run_id: str
    extraction_timestamp: str
    verified: bool
    verification_confidence: float
    verification_note: Optional[str]
    human_reviewed: bool
    tags: list[str]


# ---------------------------------------------------------------------------
# Phase 1 output — Document Registry Entry
# ---------------------------------------------------------------------------

class DocumentRegistryEntry(TypedDict):
    document_id: str           # deterministic UUID from SHA-256 of url+hash
    run_id: str
    source_url: str
    file_hash: str             # SHA-256 of raw bytes
    ingestion_timestamp: str   # ISO 8601 UTC
    jurisdiction: str
    issuing_authority: str
    regulation_name: str
    instrument_code: Optional[str]
    year_issued: int
    document_type: str
    document_type_confidence: float
    regulatory_domain: str
    topic_category: str
    applies_to: list[str]
    legal_force: str
    compliance_tier: str       # Tier1 | Tier2 | Tier3
    structure_type: str        # numbered_clauses | lettered_paragraphs | prose | mixed
    has_annexures: bool
    companion_docs: list[str]
    reporting_standards: Optional[str]
    chunk_strategy: Optional[ChunkStrategy]
    flagged_for_review: bool
    raw_text: str              # normalised UTF-8 full text (in-memory only)


# ---------------------------------------------------------------------------
# Top-level pipeline state
# ---------------------------------------------------------------------------

class PipelineState(TypedDict):
    # ── inputs ───────────────────────────────────────────────────────────────
    source_url: str
    raw_input_path: str        # local file path or empty string
    title: str
    source_authority: str

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    document: Optional[DocumentRegistryEntry]

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    chunks: list[Chunk]
    extracted_requirements: list[ExtractedRequirement]
    verified_requirements: list[VerifiedRequirement]
    human_review_queue: list[dict[str, Any]]

    # ── pipeline metadata ────────────────────────────────────────────────────
    errors: list[str]
    pipeline_complete: bool
