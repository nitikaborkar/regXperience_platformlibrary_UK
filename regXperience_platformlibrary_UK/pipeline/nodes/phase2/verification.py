"""
Node 2.4 — Verification Pass
Hallucination guard: second LLM call.
Given the requirement_text and the source chunk, verify that the
requirement text actually appears verbatim (or near-verbatim) in the source.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import ExtractedRequirement, PipelineState, VerifiedRequirement


def _chunk_text_for(state: PipelineState, chunk_id: str) -> str:
    """Look up the source chunk text by chunk_id."""
    for chunk in state["chunks"]:
        if chunk["chunk_id"] == chunk_id:
            return chunk["text"]
    return ""


def _make_requirement_id(document_id: str, section_ref: str | None, req_text: str) -> str:
    import hashlib
    seed = f"{document_id}:{section_ref}:{req_text[:200]}"
    sha = hashlib.sha256(seed.encode()).hexdigest()
    return str(uuid.UUID(sha[:32]))


def verification_pass(state: PipelineState) -> PipelineState:
    doc = state["document"]
    requirements = state["extracted_requirements"]
    total = len(requirements)

    verified: list[VerifiedRequirement] = []

    system_prompt = render_prompt("verification_system")

    for i, req in enumerate(requirements):
        chunk_text = _chunk_text_for(state, req["source_chunk_id"])

        user_prompt = render_prompt(
            "verification_user",
            requirement_text=req["requirement_text"],
            chunk_text=chunk_text,
        )

        try:
            result: dict = call_llm_json(system_prompt, user_prompt)
        except Exception as exc:
            print(f"  [Verify] ⚠  Req {i+1}/{total} verification failed: {exc}")
            result = {"verified": False, "confidence": 0.0, "note": str(exc)}

        v_req = VerifiedRequirement(
            # base fields from extracted
            requirement_text=req["requirement_text"],
            section_reference=req.get("section_reference"),
            obligation_type=req["obligation_type"],
            obligation_language=req["obligation_language"],
            nature=req.get("nature", []),
            actor=req.get("actor", []),
            source_chunk_id=req["source_chunk_id"],
            page_estimate=req.get("page_estimate"),
            # verification output
            requirement_id=_make_requirement_id(
                doc["document_id"],
                req.get("section_reference"),
                req["requirement_text"],
            ),
            document_id=doc["document_id"],
            run_id=doc["run_id"],
            extraction_timestamp=datetime.now(timezone.utc).isoformat(),
            verified=bool(result.get("verified", False)),
            verification_confidence=float(result.get("confidence", 0.0)),
            verification_note=result.get("note"),
            human_reviewed=False,
            tags=[],
        )

        verified.append(v_req)

        status = "✓" if v_req["verified"] else "✗"
        print(
            f"  [Verify] {status} Req {i+1}/{total} | "
            f"confidence={v_req['verification_confidence']:.2f} | "
            f"section={v_req.get('section_reference')!r}"
        )

    passed = sum(1 for r in verified if r["verified"])
    print(f"[Verify] {passed}/{total} requirements passed verification")

    return {**state, "verified_requirements": verified}
