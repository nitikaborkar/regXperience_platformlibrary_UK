#!/usr/bin/env python3
"""
regXperience_platformlibrary_UK — Regulatory Requirement Extraction Pipeline
CLI entry point.

Usage examples
--------------
# Single PDF document
python main.py single --file /path/to/document.pdf --title "PS21/3" --authority FCA

# Single document from URL
python main.py single --url https://www.fca.org.uk/... --title "PS21/3" --authority FCA

# Batch run from a manifest JSON
python main.py batch --manifest batch_manifest.json --workers 2
"""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv  # type: ignore


def _check_env() -> None:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit(
            "ERROR: ANTHROPIC_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key."
        )
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        sys.exit(
            "ERROR: OPENAI_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key."
        )


def cmd_single(args: argparse.Namespace) -> None:
    from orchestrator import run_single

    state = run_single(
        source_url=args.url or "",
        raw_input_path=args.file or "",
        title=args.title or "",
        source_authority=args.authority or "",
    )

    if state.get("pipeline_complete"):
        doc = state.get("document") or {}
        verified = state.get("verified_requirements", [])
        flagged = state.get("human_review_queue", [])
        print(
            f"\n✅ Pipeline complete\n"
            f"   Document ID : {doc.get('document_id', 'n/a')}\n"
            f"   Run ID      : {doc.get('run_id', 'n/a')}\n"
            f"   Requirements: {len(verified)} verified | {len(flagged)} flagged\n"
            f"   Outputs in  : ./output/\n"
        )
    else:
        errors = state.get("errors", [])
        print(f"\n⚠  Pipeline did not complete. Errors:\n" + "\n".join(f"  - {e}" for e in errors))
        sys.exit(1)


def cmd_batch(args: argparse.Namespace) -> None:
    from orchestrator import load_batch_manifest, run_batch

    documents = load_batch_manifest(args.manifest)
    print(f"[Batch] Loaded {len(documents)} document(s) from {args.manifest}")
    run_batch(documents, max_workers=args.workers)


def main() -> None:
    _check_env()

    parser = argparse.ArgumentParser(
        prog="regxperience",
        description="UK Regulatory Requirement Extraction Pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── single ────────────────────────────────────────────────────────────────
    p_single = sub.add_parser("single", help="Run pipeline on one document")
    source_group = p_single.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", metavar="PATH", help="Local file path (PDF, HTML, TXT)")
    source_group.add_argument("--url", metavar="URL", help="Remote document URL")
    p_single.add_argument("--title", metavar="TITLE", default="", help="Document title")
    p_single.add_argument("--authority", metavar="AUTH", default="", help="Issuing authority (e.g. FCA)")

    # ── batch ─────────────────────────────────────────────────────────────────
    p_batch = sub.add_parser("batch", help="Run pipeline on multiple documents from a manifest")
    p_batch.add_argument("--manifest", required=True, metavar="PATH", help="Path to batch manifest JSON")
    p_batch.add_argument("--workers", type=int, default=2, metavar="N", help="Parallel workers (default 2)")

    args = parser.parse_args()

    if args.command == "single":
        cmd_single(args)
    elif args.command == "batch":
        cmd_batch(args)


if __name__ == "__main__":
    main()
