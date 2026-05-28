"""
Node 2.6 — Write Requirements
Three outputs per run:
  1. output/requirements/{doc_id}_{run_id}.jsonl   — one requirement per line
  2. output/requirements/{doc_id}_{run_id}.xlsx    — Excel for human review
  3. output/human_review/{doc_id}_{run_id}_review.jsonl  — flagged items
  4. output/runs/{run_id}.json                     — pipeline run manifest
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.state import PipelineState

REQUIREMENTS_DIR = Path(__file__).parents[4] / "output" / "requirements"
HUMAN_REVIEW_DIR = Path(__file__).parents[4] / "output" / "human_review"
RUNS_DIR = Path(__file__).parents[4] / "output" / "runs"

for _d in (REQUIREMENTS_DIR, HUMAN_REVIEW_DIR, RUNS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Columns written to Excel — order matters
_EXCEL_COLUMNS = [
    "req_id", "doc_id", "source_chunk_id", "clause_reference",
    "requirement_text", "source_verbatim", "bnm_tag",
    "jurisdiction", "domain", "sub_domain", "legal_force",
    "requirement_category", "applies_to", "keywords",
    "verified", "similarity_score", "verbatim_present",
    "verification_note", "page_estimate", "extracted_at",
]


def _to_str(val) -> str:
    """Flatten list fields to comma-separated strings for Excel."""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    if val is None:
        return ""
    return str(val)


def _write_excel(path: Path, requirements: list[dict]) -> None:
    try:
        import openpyxl  # type: ignore
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("[WriteReqs] ⚠  openpyxl not installed — skipping Excel output. pip install openpyxl")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Requirements"

    # Header row
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    for col_idx, col_name in enumerate(_EXCEL_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    # Data rows
    for row_idx, req in enumerate(requirements, start=2):
        for col_idx, col_name in enumerate(_EXCEL_COLUMNS, start=1):
            val = _to_str(req.get(col_name))
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    # Auto-width (capped at 60)
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    ws.freeze_panes = "A2"
    wb.save(path)


def write_requirements(state: PipelineState) -> PipelineState:
    doc = state["document"]
    doc_id = doc["doc_id"]
    run_id = doc["run_id"]

    verified = state["verified_requirements"]
    human_review = state.get("human_review_queue", [])

    # ── 1. JSONL ──────────────────────────────────────────────────────────────
    jsonl_path = REQUIREMENTS_DIR / f"{doc_id}_{run_id}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for req in verified:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    # ── 2. Excel ──────────────────────────────────────────────────────────────
    xlsx_path = REQUIREMENTS_DIR / f"{doc_id}_{run_id}.xlsx"
    _write_excel(xlsx_path, [dict(r) for r in verified])
    print(f"[WriteReqs] Excel → {xlsx_path.name} ({len(verified)} rows)")

    # ── 3. Human review JSONL ─────────────────────────────────────────────────
    if human_review:
        hr_path = HUMAN_REVIEW_DIR / f"{doc_id}_{run_id}_review.jsonl"
        with hr_path.open("w", encoding="utf-8") as f:
            for item in human_review:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[WriteReqs] Human review → {hr_path.name} ({len(human_review)} items)")

    # ── 4. Run manifest ───────────────────────────────────────────────────────
    summary = {
        "run_id": run_id,
        "doc_id": doc_id,
        "document_title": doc.get("document_title", ""),
        "model_name": _model_name(),
        "prompt_version": _prompt_version(),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": doc.get("total_chunks", 0),
        "requirements_extracted": len(state.get("extracted_requirements", [])),
        "requirements_verified": len(verified),
        "requirements_flagged": len(human_review),
        "errors": state.get("errors", []),
    }
    run_path = RUNS_DIR / f"{run_id}.json"
    run_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"[WriteReqs] {len(verified)} requirements → {jsonl_path.name}\n"
        f"[WriteReqs] Run manifest → {run_path.name}"
    )

    return {**state, "pipeline_complete": True}


def _model_name() -> str:
    import os
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    return os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5") if provider == "anthropic" else os.getenv("OPENAI_MODEL", "gpt-4o")


def _prompt_version() -> str:
    import os
    return os.getenv("PROMPT_VERSION", "v1.0.0")