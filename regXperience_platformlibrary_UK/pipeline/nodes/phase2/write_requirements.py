"""
Node 2.6 — Write Requirements
Persist each verified requirement to the versioned JSONL store.
Also writes the human_review queue and a pipeline_run summary record.
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


def write_requirements(state: PipelineState) -> PipelineState:
    doc = state["document"]
    document_id = doc["document_id"]
    run_id = doc["run_id"]

    verified = state["verified_requirements"]
    human_review = state.get("human_review_queue", [])

    # ── requirements JSONL ────────────────────────────────────────────────────
    req_path = REQUIREMENTS_DIR / f"{document_id}_{run_id}.jsonl"
    with req_path.open("w", encoding="utf-8") as f:
        for req in verified:
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    # ── human review JSONL ────────────────────────────────────────────────────
    if human_review:
        hr_path = HUMAN_REVIEW_DIR / f"{document_id}_{run_id}_review.jsonl"
        with hr_path.open("w", encoding="utf-8") as f:
            for item in human_review:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[WriteReqs] Human review → {hr_path.name} ({len(human_review)} items)")

    # ── pipeline run summary ──────────────────────────────────────────────────
    chunk_strategy = doc.get("chunk_strategy") or {}
    summary = {
        "run_id": run_id,
        "document_id": document_id,
        "regulation_name": doc.get("regulation_name", ""),
        "model_name": _model_name(),
        "prompt_template_version": _prompt_version(),
        "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_chunks": chunk_strategy.get("total_chunks", 0),
        "requirements_extracted": len(state.get("extracted_requirements", [])),
        "requirements_verified": len(verified),
        "requirements_flagged": len(human_review),
        "errors": state.get("errors", []),
    }
    run_path = RUNS_DIR / f"{run_id}.json"
    run_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"[WriteReqs] {len(verified)} requirements → {req_path.name}\n"
        f"[WriteReqs] Run summary → {run_path.name}"
    )

    return {**state, "pipeline_complete": True}


def _model_name() -> str:
    import os
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def _prompt_version() -> str:
    import os
    return os.getenv("PROMPT_VERSION", "v1.0.0")
