# regXperience_platformlibrary_UK
### Regulatory Requirement Extraction Pipeline — UK Jurisdiction

A two-phase LangGraph pipeline that ingests UK regulatory documents (PDF, HTML, plain text), classifies them, extracts structured metadata, and pulls out every regulatory requirement — verbatim — with obligation type, actor, section reference, and a hallucination-guard verification pass.

---

## Architecture

```
Phase 1 — Document Intelligence
  1.1  Ingest               → normalise to UTF-8, compute SHA-256, assign document_id / run_id
  1.2  Classify Document Type → LLM: classify Act / Rules / Guidance / … + confidence score
       ↓ if confidence < 0.75 → BLOCKED (human review required)
  1.3  Extract Metadata     → LLM: jurisdiction, authority, legal_force, domain, applies_to …
  1.4  Structure Analysis   → heuristic: numbered_clauses / lettered_paragraphs / prose / mixed
  1.5  Write Registry Entry → persist JSON to output/registry/

Phase 2 — Requirement Extraction
  2.1  Chunker              → split by clause boundary (numbered docs) or fixed 1500-token windows
  2.2  Requirement Extractor → LLM per chunk: extract requirements as structured JSON
  2.3  Deduplication        → cosine similarity (sentence-transformers) or Jaccard fallback, threshold 0.92
  2.4  Verification Pass    → LLM hallucination guard: verify verbatim presence in source chunk
  2.5  Review Gate          → route: confidence < 0.80 → human_review queue
  2.6  Write Requirements   → persist JSONL to output/requirements/ + run manifest
```

---

## Setup

### 1. Clone / create the repo
```bash
git clone <your-remote-url> regXperience_platformlibrary_UK
cd regXperience_platformlibrary_UK
```

### 2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> `sentence-transformers` (for accurate deduplication) downloads ~90 MB on first run.
> If you skip it the pipeline falls back to Jaccard bigram similarity automatically.

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (or OPENAI_API_KEY)
```

---

## Running the pipeline

### Single document — local file
```bash
python main.py single --file /path/to/document.pdf \
                      --title "PS21/3 — A new Consumer Duty" \
                      --authority FCA
```

### Single document — URL
```bash
python main.py single --url https://www.fca.org.uk/publication/policy/ps21-3.pdf \
                      --title "PS21/3 — A new Consumer Duty" \
                      --authority FCA
```

### Batch run
```bash
# Edit batch_manifest.example.json → batch_manifest.json
python main.py batch --manifest batch_manifest.json --workers 3
```

---

## Outputs

| Path | Contents |
|------|----------|
| `output/registry/{document_id}.json` | Document registry entry (Phase 1 output) |
| `output/requirements/{document_id}_{run_id}.jsonl` | Verified requirements (one JSON object per line) |
| `output/human_review/{document_id}_{run_id}_review.jsonl` | Requirements flagged for human review |
| `output/runs/{run_id}.json` | Pipeline run manifest (counts, model, prompt version) |

---

## Key environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | — | Required if using Anthropic |
| `ANTHROPIC_MODEL` | `claude-opus-4-5` | Model string |
| `OPENAI_API_KEY` | — | Required if using OpenAI |
| `OPENAI_MODEL` | `gpt-4o` | Model string |
| `PROMPT_VERSION` | `v1.0.0` | Prompt template version (for reproducibility) |

---

## Prompt templates

All prompts live in `prompts/` with filename pattern `{PROMPT_VERSION}_{name}.txt`.
To create a new prompt version, copy the files and bump the semver prefix. The run manifest records which version was used, enabling exact reproduction.

---

## Open questions (from design spec)

See Section 4 of the pipeline specification. The most impactful unresolved decisions are:

- **Q1 Chunking** — semantic chunker vs fixed token windows (decide after pilot on 3–5 documents)
- **Q2 Scale** — rate-limiting wrapper needed if processing 400+ documents concurrently
- **Q3 Framework** — LangGraph is default; custom Python orchestrator is the documented fallback
- **Q5 Intermediate storage** — chunk outputs are not currently persisted (30-day TTL option from spec not yet implemented)
- **Q6 Effective obligation type** — `effective_obligation_type` derived field (`Guidance` + `Binding-SupervisoryExpectations` → `Mandatory-Effective`) is not yet in the schema; add when downstream consumers are ready
