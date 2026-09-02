# prep-app-be

FastAPI backend for the Learning Tool - the AI engine behind it.

## What it does

Given any topic, produces a complete study set for it: subtopics, each with a written explanation followed by practice Q&A, generated on demand by a multi-step LLM agent pipeline (no agent framework - plain Python orchestration):

1. **Retrieve** - embed the topic and pull the nearest reference chunks from a Chroma vector index, to ground generation in real material rather than the model's own recall.
2. **Plan** - the LLM decomposes the topic into a set of non-overlapping subtopics that together give comprehensive coverage.
3. **Generate** - questions and answers are generated across those subtopics, grounded in the retrieved chunks, deliberately over-generated since the next step will trim some.
4. **Dedupe & refine** - every candidate question is embedded and near-duplicates are dropped by cosine similarity; if that drops the set below target, a follow-up LLM call tops it back up, told explicitly what's already covered so it doesn't reintroduce what was just removed.
5. **Categorize** - a normalization pass merges near-duplicate category names into a clean taxonomy across the whole set.
6. **Explain** - a written explanation is generated for each final subtopic, grounded in the same reference material, so the output reads like a real study guide rather than a bare Q&A dump.
7. **Eval** - every run is self-graded: an LLM-as-judge relevance score per question, plus an embedding-similarity duplication check, both reported back to the caller as run metadata (not silently discarded).

Every step is instrumented - per-step latency and token usage is captured and logged as structured JSON, and returned with the response. Results are cached per topic (Postgres) so the same topic is never regenerated twice, and a set of core topics ships with hand-authored, pre-loaded content that is indistinguishable in shape from generated output. Every free-text topic also passes through a two-layer AI safety classifier before it ever reaches the pipeline.

A separate **Hybrid Search** feature (`/api/quick-search`) runs hybrid retrieval over the same reference corpus: BM25 keyword search (OpenSearch) and vector search (the same Chroma index/embeddings above) fused via reciprocal-rank or weighted fusion, with an optional LLM re-ranking pass, and search-quality evaluation (NDCG@k, Precision@k, Recall@k) against a small hand-labeled query set. Entirely additive - a separate router, its own OpenSearch dependency (local via Docker, see `docker-compose.yml`), no changes to any existing route or table.

## Tech stack

- **Framework**: FastAPI (Python), fully async-capable REST API.
- **Agent orchestration**: a hand-rolled multi-step agent loop (plan -> generate -> dedupe/refine -> categorize -> explain -> eval) - no LangChain/LangGraph dependency in this service; every step is independently typed, independently testable, and independently observable.
- **LLM abstraction**: three providers - Anthropic Claude, Google Gemini, and Groq - unified behind one `call_structured()` interface returning schema-validated Pydantic objects. Swapping providers is a single config value; no pipeline code changes, no prompt duplication. Provider-specific quirks (e.g. Groq's stricter JSON-schema requirements) are normalized away at the client boundary, not leaked into calling code.
- **RAG / vector search**: Chroma, embedding both a reference corpus (for grounding generation) and every generated question (for duplicate detection) via the same embedding function - one retrieval mechanism serving two different jobs in the pipeline.
- **Embeddings**: Google's embedding API, decoupled from whichever provider is generating text - the embedding model and the generation model can differ.
- **Evaluation**: LLM-as-judge scoring plus quantitative embedding-similarity duplication detection, run automatically on every generation, not a separate offline process.
- **AI safety**: a fail-closed guardrail on all free-text input - a fast keyword pre-filter plus an LLM classification pass - that must explicitly pass before any generation call is made.
- **Observability**: structured, per-step JSON logging (latency + token counts per LLM call) accumulated into a run-level report returned alongside every API response.
- **Database/ORM**: Postgres (Neon) via SQLModel - backs the topic cache, category taxonomy, and per-user history.
- **Hybrid search**: OpenSearch (BM25) for Hybrid Search's keyword leg, fused with the existing Chroma vector leg - local-only via Docker, opt-in, connects lazily so its absence never affects any other route.
- **Auth**: JWT bearer tokens with bcrypt password hashing.
- **Deployment**: Render.
