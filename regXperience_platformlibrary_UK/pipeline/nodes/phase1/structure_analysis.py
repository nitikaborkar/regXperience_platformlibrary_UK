"""
Node 1.4 — Structure Analysis
Heuristic pass: detect whether the document uses numbered clauses,
lettered paragraphs, plain prose, or a mix.
Sets structure_type flag consumed by the Chunker in Phase 2.
"""

from __future__ import annotations
import re

from pipeline.state import PipelineState

# Patterns that indicate numbered clause hierarchy (e.g. SYSC 15A.2.1, 3.1.2, Article 5(2)(a))
_NUMBERED_CLAUSE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:"
    r"[A-Z]{2,6}\s*\d[\w.]*\s*[A-Z]?\s*\.?\d"  # FCA/PRA style: SYSC 15A.2.1
    r"|(?:Article|Section|Clause|Rule|Para(?:graph)?)\s+\d+"  # Article 5, Section 3
    r"|\d+\.\d+(?:\.\d+)+"                                     # 3.1.2.4
    r")",
    re.IGNORECASE,
)

# Lettered paragraph markers: (a), (b), a), b)
_LETTERED_PARA_PATTERN = re.compile(
    r"(?:^|\n)\s*\((?:[a-zA-Z]|[ivxlIVXL]+)\)\s",
)

# Section headings (bold all-caps or Title Case line)
_HEADING_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[A-Z][A-Z\s,&\-]{4,}|(?:\d+\.?\s+)?[A-Z][a-zA-Z\s]{3,})\s*(?:\n|$)",
)


def structure_analysis(state: PipelineState) -> PipelineState:
    doc = dict(state["document"])
    text = doc["raw_text"]

    # Sample first 20k chars for heuristics (fast)
    sample = text[:20_000]

    numbered_hits = len(_NUMBERED_CLAUSE_PATTERN.findall(sample))
    lettered_hits = len(_LETTERED_PARA_PATTERN.findall(sample))

    if numbered_hits >= 5:
        if lettered_hits >= 5:
            structure_type = "mixed"
        else:
            structure_type = "numbered_clauses"
    elif lettered_hits >= 5:
        structure_type = "lettered_paragraphs"
    else:
        structure_type = "prose"

    # Detect annexures / appendices
    has_annexures = bool(
        re.search(r"\b(?:annex(?:ure)?|appendix|schedule)\b", text, re.IGNORECASE)
    )

    doc["structure_type"] = structure_type
    doc["has_annexures"] = has_annexures

    print(
        f"[Structure] structure_type={structure_type!r} | "
        f"has_annexures={has_annexures} | "
        f"numbered_hits={numbered_hits} | lettered_hits={lettered_hits}"
    )

    return {**state, "document": doc}
