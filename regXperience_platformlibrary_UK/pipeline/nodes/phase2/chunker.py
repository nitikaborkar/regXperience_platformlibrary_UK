"""
Node 2.1 — Chunker
Split document into chunks.
Strategy depends on structure_type set in Phase 1:
  - numbered_clauses  → chunk at clause boundaries, max 2,000 tokens
  - prose / mixed     → fixed 1,500 tokens with 300-token overlap
  - lettered_paragraphs → fixed 1,500 tokens with 300-token overlap
"""

from __future__ import annotations
import re
import uuid
from typing import Optional

from pipeline.state import Chunk, ChunkStrategy, PipelineState

# 1 token ≈ 4 chars (rough but good enough for chunking)
_CHARS_PER_TOKEN = 4

_PROSE_CHUNK_TOKENS = 1_500
_PROSE_OVERLAP_TOKENS = 300
_CLAUSE_MAX_TOKENS = 2_000

# Numbered clause boundary: lines starting with FCA/PRA ref or 1.2.3 style
_CLAUSE_BOUNDARY = re.compile(
    r"(?:^|\n)(?="
    r"[A-Z]{2,6}\s*\d[\w.]*\s*[A-Z]?\s*\.?\d"       # SYSC 15A.2.1
    r"|(?:Article|Section|Clause|Rule)\s+\d+"          # Article 5
    r"|\d+\.\d+(?:\.\d+)*\s"                           # 3.1.2
    r")",
    re.MULTILINE | re.IGNORECASE,
)

_HEADING_PATTERN = re.compile(r"(?:^|\n)(#{1,4}\s+.+|[A-Z][A-Z\s,&\-]{4,})\s*(?=\n)", re.MULTILINE)


def _detect_section_heading(text: str) -> Optional[str]:
    """Return the first heading-like line in a text snippet."""
    m = _HEADING_PATTERN.search(text[:500])
    return m.group(1).strip() if m else None


def _estimate_page(offset: int, total_chars: int, assumed_pages: int = 30) -> int:
    """Very rough page estimate based on character offset."""
    return max(1, round((offset / max(total_chars, 1)) * assumed_pages) + 1)


def _fixed_size_chunks(text: str, chunk_tokens: int, overlap_tokens: int) -> list[Chunk]:
    chunk_chars = chunk_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN
    step = chunk_chars - overlap_chars
    total = len(text)
    chunks: list[Chunk] = []
    idx = 0
    pos = 0

    while pos < total:
        end = min(pos + chunk_chars, total)
        snippet = text[pos:end]
        chunks.append(Chunk(
            chunk_id=str(uuid.uuid4()),
            chunk_index=idx,
            text=snippet,
            byte_offset_start=pos,
            byte_offset_end=end,
            page_estimate=_estimate_page(pos, total),
            section_heading=_detect_section_heading(snippet),
        ))
        idx += 1
        pos += step
        if end == total:
            break

    return chunks


def _clause_chunks(text: str, max_tokens: int) -> list[Chunk]:
    max_chars = max_tokens * _CHARS_PER_TOKEN
    # Split on clause boundaries
    boundaries = [m.start() for m in _CLAUSE_BOUNDARY.finditer(text)]
    if not boundaries:
        # Fallback to fixed chunking
        return _fixed_size_chunks(text, max_tokens, max_tokens // 5)

    # Build segments between boundaries
    segments: list[str] = []
    starts: list[int] = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        segments.append(text[start:end])
        starts.append(start)

    # Merge small segments; split oversized ones
    chunks: list[Chunk] = []
    idx = 0
    buf = ""
    buf_start = starts[0] if starts else 0

    for seg, seg_start in zip(segments, starts):
        if len(buf) + len(seg) <= max_chars:
            if not buf:
                buf_start = seg_start
            buf += seg
        else:
            if buf:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    chunk_index=idx,
                    text=buf,
                    byte_offset_start=buf_start,
                    byte_offset_end=buf_start + len(buf),
                    page_estimate=_estimate_page(buf_start, len(text)),
                    section_heading=_detect_section_heading(buf),
                ))
                idx += 1
            # If segment itself is oversized, split it
            if len(seg) > max_chars:
                sub = _fixed_size_chunks(seg, max_tokens, max_tokens // 5)
                for s in sub:
                    s["chunk_index"] = idx
                    s["byte_offset_start"] += seg_start
                    s["byte_offset_end"] += seg_start
                    s["chunk_id"] = str(uuid.uuid4())
                    chunks.append(s)
                    idx += 1
                buf = ""
            else:
                buf = seg
                buf_start = seg_start

    if buf:
        chunks.append(Chunk(
            chunk_id=str(uuid.uuid4()),
            chunk_index=idx,
            text=buf,
            byte_offset_start=buf_start,
            byte_offset_end=buf_start + len(buf),
            page_estimate=_estimate_page(buf_start, len(text)),
            section_heading=_detect_section_heading(buf),
        ))

    return chunks


def chunker(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])
    text = doc["raw_text"]
    structure_type = doc.get("structure_type", "prose")

    if structure_type == "numbered_clauses":
        chunks = _clause_chunks(text, _CLAUSE_MAX_TOKENS)
        chunk_size_tokens = _CLAUSE_MAX_TOKENS
        overlap_tokens = 0
    else:
        chunks = _fixed_size_chunks(text, _PROSE_CHUNK_TOKENS, _PROSE_OVERLAP_TOKENS)
        chunk_size_tokens = _PROSE_CHUNK_TOKENS
        overlap_tokens = _PROSE_OVERLAP_TOKENS

    strategy: ChunkStrategy = {
        "chunk_size_tokens": chunk_size_tokens,
        "overlap_tokens": overlap_tokens,
        "total_chunks": len(chunks),
    }
    doc["chunk_strategy"] = strategy

    print(
        f"[Chunker] structure_type={structure_type!r} | "
        f"{len(chunks)} chunks | "
        f"chunk_size={chunk_size_tokens} tokens | overlap={overlap_tokens}"
    )

    return {**state, "document": doc, "chunks": chunks}
