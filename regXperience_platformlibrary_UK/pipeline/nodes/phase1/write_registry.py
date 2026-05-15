"""
Node 1.5 — Write Registry Entry
Persist the completed document registry entry to the versioned JSON store.
Strips the large raw_text field before writing to disk.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.state import PipelineState

REGISTRY_DIR = Path(__file__).parents[4] / "output" / "registry"
REGISTRY_DIR.mkdir(parents=True, exist_ok=True)


def write_registry(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])

    # Persist without raw_text (too large for the store)
    persisted = {k: v for k, v in doc.items() if k != "raw_text"}

    out_path = REGISTRY_DIR / f"{doc['document_id']}.json"
    out_path.write_text(json.dumps(persisted, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[Registry] Written → {out_path.name}")

    return {**state, "document": doc}
