"""
Node 1.5 — Write Registry Entry
Persist the completed document registry entry to output/registry/{doc_id}.json
Strips internal-only fields before writing.
"""

from __future__ import annotations
import json
from pathlib import Path

from pipeline.state import PipelineState

REGISTRY_DIR = Path(__file__).parents[4] / "output" / "registry"
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

# Fields that exist only for pipeline-internal use — never written to disk
_INTERNAL_FIELDS = {"raw_text", "file_hash", "run_id", "flagged_for_review", "instrument_type_confidence"}


def write_registry(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])

    persisted = {k: v for k, v in doc.items() if k not in _INTERNAL_FIELDS}

    out_path = REGISTRY_DIR / f"{doc['doc_id']}.json"
    out_path.write_text(json.dumps(persisted, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Registry] Written → {out_path.name}")

    return {**state, "document": doc}