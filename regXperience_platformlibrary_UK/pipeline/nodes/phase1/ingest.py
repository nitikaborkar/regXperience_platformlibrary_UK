"""
Node 1.1 — Ingest
Accept document input (PDF, HTML, plain text).
Normalise to UTF-8 plain text.
Record source URL, file hash (SHA-256), and ingestion timestamp.
"""

from __future__ import annotations
import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pipeline.state import PipelineState


# ── Optional extraction helpers (graceful degradation) ──────────────────────

def _extract_pdf(path: str) -> str:
    try:
        import pdfplumber  # type: ignore
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except ImportError:
        pass
    # fallback: pypdf
    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(path)
        return "\n".join(
            p.extract_text() or "" for p in reader.pages
        )
    except ImportError:
        pass
    raise RuntimeError(
        "No PDF extraction library found. "
        "Install pdfplumber: pip install pdfplumber"
    )


def _extract_html(raw: bytes) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        import re
        text = raw.decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", text)


def _read_raw_bytes(state: PipelineState) -> tuple[bytes, str]:
    """Return (raw_bytes, extension)."""
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

    raise ValueError("Ingest node: provide either raw_input_path or source_url.")


# ── Node ─────────────────────────────────────────────────────────────────────

def ingest(state: PipelineState) -> PipelineState:
    """Ingest node — normalise document to UTF-8 plain text."""

    raw_bytes, ext = _read_raw_bytes(state)

    # ── extract text ──────────────────────────────────────────────────────────
    if ext == ".pdf":
        # write temp file if we got bytes from URL
        if not state.get("raw_input_path"):
            tmp = Path("/tmp/_ingest_doc.pdf")
            tmp.write_bytes(raw_bytes)
            text = _extract_pdf(str(tmp))
        else:
            text = _extract_pdf(state["raw_input_path"])
    elif ext in (".html", ".htm"):
        text = _extract_html(raw_bytes)
    else:
        # plain text / markdown / XML — decode as UTF-8
        text = raw_bytes.decode("utf-8", errors="replace")

    text = text.strip()
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    # ── deterministic document_id from URL + hash ─────────────────────────────
    source_url = state.get("source_url", state.get("raw_input_path", ""))
    seed = f"{source_url}:{file_hash}"
    document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
    run_id = str(uuid.uuid4())

    # ── partial registry entry (Phase 1 nodes will fill the rest) ────────────
    document: dict = {
        "document_id": document_id,
        "run_id": run_id,
        "source_url": source_url,
        "file_hash": file_hash,
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        # Phase 1 nodes fill these:
        "jurisdiction": "",
        "issuing_authority": state.get("source_authority", ""),
        "regulation_name": state.get("title", ""),
        "instrument_code": None,
        "year_issued": 0,
        "document_type": "",
        "document_type_confidence": 0.0,
        "regulatory_domain": "",
        "topic_category": "",
        "applies_to": [],
        "legal_force": "",
        "compliance_tier": "Tier2",
        "structure_type": "",
        "has_annexures": False,
        "companion_docs": [],
        "reporting_standards": None,
        "chunk_strategy": None,
        "flagged_for_review": False,
        "raw_text": text,
    }

    print(f"[Ingest] document_id={document_id} | hash={file_hash[:12]}… | {len(text):,} chars")

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
