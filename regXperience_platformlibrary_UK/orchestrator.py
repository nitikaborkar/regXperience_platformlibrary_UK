"""
Batch orchestrator.
Accepts a list of document descriptors and runs one pipeline graph
per document. Handles concurrency via a thread pool.
"""

from __future__ import annotations
import concurrent.futures
import json
from pathlib import Path
from typing import Any

from pipeline.graph import compile_graph
from pipeline.state import PipelineState


def run_single(
    source_url: str = "",
    raw_input_path: str = "",
    title: str = "",
    source_authority: str = "",
) -> dict[str, Any]:
    """Run the full pipeline for one document. Returns the final state."""
    app = compile_graph()

    initial: PipelineState = {
        "source_url": source_url,
        "raw_input_path": raw_input_path,
        "title": title,
        "source_authority": source_authority,
        "document": None,
        "chunks": [],
        "extracted_requirements": [],
        "verified_requirements": [],
        "human_review_queue": [],
        "errors": [],
        "pipeline_complete": False,
    }

    final_state = app.invoke(initial)
    return final_state


def run_batch(
    documents: list[dict[str, str]],
    max_workers: int = 2,
) -> list[dict[str, Any]]:
    """
    Run the pipeline for a batch of documents in parallel.

    Each document dict should have keys:
      source_url, raw_input_path, title, source_authority
    """
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_single, **doc): doc
            for doc in documents
        }
        for future in concurrent.futures.as_completed(futures):
            doc = futures[future]
            label = doc.get("title") or doc.get("source_url") or doc.get("raw_input_path", "?")
            try:
                state = future.result()
                status = "✓ complete" if state["pipeline_complete"] else "⚠ blocked"
                print(f"\n[Batch] {label!r} → {status}")
                results.append(state)
            except Exception as exc:
                print(f"\n[Batch] {label!r} → ✗ ERROR: {exc}")
                results.append({"error": str(exc), "doc": doc})

    return results


def load_batch_manifest(path: str) -> list[dict[str, str]]:
    """
    Load a JSON batch manifest.
    Format:
    [
      {
        "source_url": "https://...",
        "raw_input_path": "",
        "title": "PS21/3 ...",
        "source_authority": "FCA"
      },
      ...
    ]
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Batch manifest must be a JSON array of document objects.")
    return data
