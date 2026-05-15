"""
LangGraph graph definition.
Wires Phase 1 and Phase 2 nodes with conditional edges for:
  - document type confidence gate (< 0.75 → human review, block Phase 2)
  - verification confidence gate  (handled in review_gate node)
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph  # type: ignore

from pipeline.state import PipelineState

# Phase 1
from pipeline.nodes.phase1.ingest import ingest
from pipeline.nodes.phase1.classify import classify_document_type
from pipeline.nodes.phase1.extract_metadata import extract_metadata
from pipeline.nodes.phase1.structure_analysis import structure_analysis
from pipeline.nodes.phase1.write_registry import write_registry

# Phase 2
from pipeline.nodes.phase2.chunker import chunker
from pipeline.nodes.phase2.requirement_extractor import requirement_extractor
from pipeline.nodes.phase2.deduplication import deduplication
from pipeline.nodes.phase2.verification import verification_pass
from pipeline.nodes.phase2.review_gate import review_gate
from pipeline.nodes.phase2.write_requirements import write_requirements


# ── Conditional edge functions ────────────────────────────────────────────────

def _after_classify(state: PipelineState) -> str:
    """If document type confidence is too low, park in human review."""
    if state["document"].get("flagged_for_review", False):
        return "human_review_blocked"
    return "extract_metadata"


def _human_review_blocked(state: PipelineState) -> PipelineState:
    """Terminal node for documents blocked pending human review."""
    print(
        "\n⚠  Pipeline paused — document flagged for human review.\n"
        "   Resolve the document_type classification in the registry entry,\n"
        "   then re-run with --resume to continue Phase 2.\n"
    )
    return {**state, "pipeline_complete": False}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(PipelineState)

    # ── Phase 1 nodes ─────────────────────────────────────────────────────────
    g.add_node("ingest", ingest)
    g.add_node("classify_document_type", classify_document_type)
    g.add_node("extract_metadata", extract_metadata)
    g.add_node("structure_analysis", structure_analysis)
    g.add_node("write_registry", write_registry)

    # ── Phase 2 nodes ─────────────────────────────────────────────────────────
    g.add_node("chunker", chunker)
    g.add_node("requirement_extractor", requirement_extractor)
    g.add_node("deduplication", deduplication)
    g.add_node("verification_pass", verification_pass)
    g.add_node("review_gate", review_gate)
    g.add_node("write_requirements", write_requirements)

    # ── Human review blocked terminal ─────────────────────────────────────────
    g.add_node("human_review_blocked", _human_review_blocked)

    # ── Edges — Phase 1 ───────────────────────────────────────────────────────
    g.set_entry_point("ingest")
    g.add_edge("ingest", "classify_document_type")

    g.add_conditional_edges(
        "classify_document_type",
        _after_classify,
        {
            "extract_metadata": "extract_metadata",
            "human_review_blocked": "human_review_blocked",
        },
    )

    g.add_edge("extract_metadata", "structure_analysis")
    g.add_edge("structure_analysis", "write_registry")

    # ── Edges — Phase 1 → Phase 2 ─────────────────────────────────────────────
    g.add_edge("write_registry", "chunker")

    # ── Edges — Phase 2 ───────────────────────────────────────────────────────
    g.add_edge("chunker", "requirement_extractor")
    g.add_edge("requirement_extractor", "deduplication")
    g.add_edge("deduplication", "verification_pass")
    g.add_edge("verification_pass", "review_gate")
    g.add_edge("review_gate", "write_requirements")
    g.add_edge("write_requirements", END)

    # Terminal for blocked documents
    g.add_edge("human_review_blocked", END)

    return g


def compile_graph():
    """Return a compiled, runnable LangGraph app."""
    return build_graph().compile()
