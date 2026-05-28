"""
Node 1.1 — Ingest
Accept document input (PDF, HTML, plain text).
Normalise to UTF-8 plain text.
Record file path, source URL, file hash (SHA-256), and ingestion timestamp.
"""

from __future__ import annotations
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pipeline.state import PipelineState


# ── Optional extraction helpers ───────────────────────────────────────────────

def _extract_pdf(path: str) -> tuple[str, int]:
    """Returns (text, page_count)."""
    try:
        import pdfplumber  # type: ignore
        text_parts = []
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts), page_count
    except ImportError:
        pass
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(path)
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        return text, len(reader.pages)
    except ImportError:
        pass
    raise RuntimeError("No PDF library found. pip install pdfplumber")


def _extract_html(raw: bytes) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        import re
        return re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace"))


def _read_raw_bytes(state: PipelineState) -> tuple[bytes, str]:
    path = state.get("raw_input_path", "")
    url = state.get("source_url", "")

    if path and Path(path).exists():
        raw = Path(path).read_bytes()
        ext = Path(path).suffix.lower()
        return raw, ext

    if url:
        import urllib.request
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
            raw = resp.read()
        ext = ".html" if "text/html" in resp.headers.get("Content-Type", "") else ".txt"
        return raw, ext

    raise ValueError("Ingest: provide either raw_input_path or source_url.")


# ── Node ─────────────────────────────────────────────────────────────────────

def ingest(state: PipelineState) -> PipelineState:
    raw_bytes, ext = _read_raw_bytes(state)
    total_pages: int | None = None

    if ext == ".pdf":
        tmp_path = state.get("raw_input_path") or "/tmp/_ingest_doc.pdf"
        if not state.get("raw_input_path"):
            Path(tmp_path).write_bytes(raw_bytes)
        text, total_pages = _extract_pdf(tmp_path)
    elif ext in (".html", ".htm"):
        text = _extract_html(raw_bytes)
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    text = text.strip()
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    file_path = state.get("raw_input_path", "") or state.get("source_url", "")
    source_url = state.get("source_url") or None

    seed = f"{file_path}:{file_hash}"
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
    run_id = str(uuid.uuid4())

    document: dict = {
        "doc_id": doc_id,
        "file_path": file_path,
        "source_url": source_url,
        "jurisdiction": "",
        "issuer": state.get("source_authority", ""),
        "document_title": state.get("title", ""),
        "instrument_type": "",
        "domain": "",
        "legal_force": "",
        "effective_date": None,
        "applicable_entities": [],
        "legal_basis": [],
        "has_sg_clause_tags": False,
        "mas_notice_number": None,
        "is_cross_sector": False,
        "chunk_strategy": "fixed",
        "total_pages": total_pages,
        "total_chunks": 0,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        # internal
        "raw_text": text,
        "file_hash": file_hash,
        "run_id": run_id,
        "flagged_for_review": False,
        "instrument_type_confidence": 0.0,
    }

    print(f"[Ingest] doc_id={doc_id} | hash={file_hash[:12]}… | {len(text):,} chars | pages={total_pages}")

    return {
        **state,
        "document": document,
        "chunks": [],
        "extracted_requirements": [],
        "verified_requirements": [],
        "human_review_queue": [],
        "errors": state.get("errors", []),
        "pipeline_complete": False,
    }