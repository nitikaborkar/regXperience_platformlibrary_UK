"""
Node 2.4 — Verification Pass
Hallucination guard: second LLM call per requirement.
Verifies requirement_text appears verbatim (or near-verbatim) in the source chunk.
Stamps jurisdiction, domain, legal_force from document onto each requirement.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone

from pipeline.llm import call_llm_json
from pipeline.prompts import render_prompt
from pipeline.state import ExtractedRequirement, PipelineState, VerifiedRequirement


def _chunk_text_for(state: PipelineState, chunk_id: str) -> str:
    for chunk in state["chunks"]:
        if chunk["chunk_id"] == chunk_id:
            return chunk["text"]
    return ""


def _make_req_id(doc_id: str, clause_ref: str | None, req_text: str) -> str:
    import hashlib
    seed = f"{doc_id}:{clause_ref}:{req_text[:200]}"
    sha = hashlib.sha256(seed.encode()).hexdigest()
    return str(uuid.UUID(sha[:32]))


def verification_pass(state: PipelineState) -> PipelineState:
    doc = state["document"]
    requirements = state["extracted_requirements"]
    total = len(requirements)

    jurisdiction = doc.get("jurisdiction", "")
    domain = doc.get("domain", "")
    legal_force = doc.get("legal_force", "")

    system_prompt = render_prompt("verification_system")
    verified: list[VerifiedRequirement] = []

    for i, req in enumerate(requirements):
        chunk_text = _chunk_text_for(state, req["source_chunk_id"])

        user_prompt = render_prompt(
            "verification_user",
            requirement_text=req["requirement_text"],
            source_verbatim=req.get("source_verbatim") or "",
            chunk_text=chunk_text,
        )

        try:
            result: dict = call_llm_json(system_prompt, user_prompt)
        except Exception as exc:
            print(f"  [Verify] ⚠  Req {i+1}/{total} failed: {exc}")
            result = {"verified": False, "similarity_score": 0.0, "verbatim_present": False, "note": str(exc)}

        similarity_score = float(result.get("similarity_score", 0.0))

        v_req = VerifiedRequirement(
            # base fields from extraction
            requirement_text=req["requirement_text"],
            source_verbatim=req.get("source_verbatim"),
            clause_reference=req.get("clause_reference"),
            bnm_tag=req.get("bnm_tag"),
            sub_domain=req.get("sub_domain"),
            requirement_category=req.get("requirement_category"),
            keywords=req.get("keywords", []),
            applies_to=req.get("applies_to", []),
            source_chunk_id=req["source_chunk_id"],
            page_estimate=req.get("page_estimate"),
            # verification output
            req_id=_make_req_id(doc["doc_id"], req.get("clause_reference"), req["requirement_text"]),
            doc_id=doc["doc_id"],
            jurisdiction=jurisdiction,
            domain=domain,
            legal_force=legal_force,
            verified=bool(result.get("verified", False)),
            similarity_score=similarity_score,
            verification_note=result.get("note"),
            verbatim_present=bool(result.get("verbatim_present", similarity_score >= 0.95)),
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )

        verified.append(v_req)

        status = "✓" if v_req["verified"] else "✗"
        print(
            f"  [Verify] {status} Req {i+1}/{total} | "
            f"score={v_req['similarity_score']:.2f} | "
            f"verbatim={v_req['verbatim_present']} | "
            f"clause={v_req.get('clause_reference')!r}"
        )

    passed = sum(1 for r in verified if r["verified"])
    print(f"[Verify] {passed}/{total} requirements passed verification")

    return {**state, "verified_requirements": verified}