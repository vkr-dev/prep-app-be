# prep-app-be

FastAPI backend for the Interview-Prep Question Generator. See [context.md](../prep-app-ui/context.md) (in the UI repo) for the full project brief.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; use .venv\Scripts\activate.ps1 in PowerShell
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- `LLM_PROVIDER` - `1` (Anthropic) or `2` (Google). Only that provider's key below needs to be set.
- `ANTHROPIC_API_KEY` - from console.anthropic.com (separate from Claude.ai / Claude Code auth).
- `GOOGLE_API_KEY` - from aistudio.google.com, free tier. Good for dev/test iteration without spending Anthropic credit - same pipeline, same schemas, just cheaper/faster for exploratory runs.
- `JWT_SECRET` - `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `OWNER_EMAIL` - your login email.
- `OWNER_PASSWORD_HASH` - `python scripts/hash_password.py`, paste the printed line.
- `DATABASE_URL` - a Neon Postgres connection string (`postgresql+psycopg://...?sslmode=require`).

## Run

```bash
uvicorn app.main:app --reload
```

On startup this creates tables (if missing) and seeds the owner row from env. Docs at `http://localhost:8000/docs`.

## Try it end-to-end

```bash
# 1. Log in as owner
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "<your real password>"}'
# -> {"access_token": "...", "status": "owner", ...}

# 2. Generate questions (Bearer token from step 1)
curl -s -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"topic": "SQL"}'
```

Guest flow: `POST /api/auth/register` -> owner calls `POST /api/auth/approve/{user_id}` (1-hour window starts now) -> guest's existing token starts passing the guard. `POST /api/auth/revoke/{user_id}` cuts it off immediately.

## Structure

```
app/
  main.py           FastAPI app, CORS, owner bootstrap + Chroma index build on startup
  config.py         Settings from env (.env locally, real env vars on Render)
  db.py             SQLModel engine/session (Neon Postgres)
  models/user.py    SQLModel User table
  models/question_cache.py  SQLModel shared topic-cache table
  models/topic_label.py     SQLModel shared AI-categorized topic label table
  models/search_history.py SQLModel per-user search history table
  schemas/          Pydantic request/response models (auth, generate, pipeline, search_history)
  auth/             security (hash/JWT), deps (guard), routes (register/login/approve/revoke)
  llm/              client.py picks the active provider (LLM_PROVIDER); anthropic_client.py / google_client.py implement the same call_structured() interface
  rag/              seed corpus, Chroma retrieval, shared embedding/cosine-similarity helpers
  agent/            the 4 pipeline steps (plan/generate/dedupe-refine/categorize), eval, orchestration, shared question cache
  history/          per-user search history + shared AI topic categorization (see below)
  observability/    structured JSON logging + the RunTracker that feeds latency/token metrics
  api/routes.py     /api/health (public), /api/generate + /api/search-history (protected)
scripts/hash_password.py   generates OWNER_PASSWORD_HASH
```

## The /api/generate pipeline (Day 2)

`POST /api/generate` runs a plain-Python agent loop, no framework:

1. **RAG retrieve** - embed the topic, pull the 4 nearest chunks from a small seed corpus (`app/rag/seed_corpus.py`) via a local Chroma collection (ephemeral, rebuilt from the seed corpus on every startup). Embeddings come from Google's embedding API (`app/rag/embeddings.py`), not a locally-loaded model - a local ONNX model needs enough RAM (onnxruntime + loaded weights) to blow past Render free tier's 512MB cap, confirmed live. This makes `GOOGLE_API_KEY` required regardless of which `LLM_PROVIDER` handles question generation - Anthropic has no first-party embeddings endpoint.
2. **Plan** - the LLM breaks the topic into 4-6 subtopics.
3. **Generate** - the LLM generates questions across those subtopics, grounded in the retrieved reference chunks. Over-generates a few extra, since dedup will remove some.
4. **Dedupe/refine** - candidate questions are embedded (same Chroma embedding function as step 1) and near-duplicates (cosine similarity > 0.88) are dropped. If that drops the count below target, one more LLM call tops it back up, explicitly told what's already covered.
5. **Categorize** - the LLM normalizes category names and re-verifies each question's difficulty label across the whole set. It only returns index + labels, never question/answer text, so it can't accidentally rewrite content.
6. **Eval** - LLM-as-judge relevance score (1-5) per question, plus a cosine-similarity duplication check on the final set (flagged, not enforced - a report, not a rewrite).

"The LLM" is whichever provider `LLM_PROVIDER` selects (`app/llm/client.py`) - every step calls `call_structured()` and never imports a provider SDK directly, so this list holds regardless of which one is active.

Every step's latency and (for LLM calls) token usage is captured in a `RunTracker` and logged as one JSON line per step to stdout, plus a final `run_completed` summary line. That same data comes back in the API response (`eval` + `metrics`) for the Angular UI to render alongside the questions.

A failed provider call (bad key, rate limit, outage) surfaces as `502` with a `{"detail": "LLM provider error: ..."}` body; a response that came back but never parsed into the expected schema (safety refusal/block, or malformed JSON that survived one retry) surfaces as `502` with `{"detail": "LLM output error: ..."}`. Either way, not a bare `500` - the frontend distinguishes provider failures from an app bug.

## Shared topic cache

`POST /api/generate` checks a Postgres-backed cache (`app/agent/cache.py`, table `questionsetcache`) before running the pipeline at all. The cache key is the topic normalized (lowercased, whitespace-collapsed) - **not** per-user. The first person to ask about "SQL" pays for the full pipeline run; every later request for "SQL" (or "sql", or "  SQL  " - any user, including a different one) is served straight from the DB, with `from_cache: true` and zero token usage in the response. This is exact-match only, not embedding-similarity matching - "SQL" and "SQL joins" are different cache entries by design.

There's no cache invalidation yet - an entry lives forever until manually deleted from the table. Fine for now; a "regenerate" bypass is an easy follow-up if question sets need to be refreshed later.

## Per-user search history + AI topic categorization

`POST /api/generate` also records the search into `GET /api/search-history` (`app/history/service.py`) - unlike the question cache, this table (`searchhistory`) is per-user, since it's each user's own list of past searches. Re-searching a topic bumps its timestamp rather than duplicating it.

Every topic also gets a short label + category (`table topiclabel`) - **shared** across all users, same normalized-topic-key pattern as the question cache. The LLM is only called to assign a label the *first time anyone ever searches a topic*; every later search of it (any user) reuses the stored row. When a genuinely new topic does need labeling, the LLM is shown every existing category already in the table and told to reuse one if it fits (matched by meaning, not exact wording) - this is what makes "Java Streams" and "Java Generics" land in the same "Java" group instead of each inventing a slightly different category name.

`GenerateRequest.topic` is capped at 50 words (`app/schemas/generate.py`), enforced both server-side (a Pydantic validator) and client-side (the search page disables submit past the limit).

## Curated content (no LLM) + subtopic progress tracking

`scripts/seed_curated_topics.py` inserts hand-authored, comprehensive content directly into the DB for a few topics (currently Java, Spring Boot, RAG, LangChain) - no LLM call anywhere in that script. It reuses the exact same tables as LLM-generated content (`save_to_cache`, `TopicLabel`, `SearchHistory`), so these topics are just instant, zero-token cache hits from the moment the script runs, indistinguishable in shape from anything the pipeline produces except `GenerateResult.curated: true`, which the UI uses to show an honest "human-curated" badge instead of "served from cache." Safe to re-run - every insert is an upsert. Java and Spring Boot share the `"Java"` category (and RAG/LangChain share `"AI/LLM"`), so they group together on the search page exactly like same-topic LLM-categorized searches would.

Each curated topic is organized into subtopics (the `Question.category` field doubles as the subtopic name), each with two parts: real reading content (`GenerateResult.subtopic_content`, a `SubtopicContent` list of `{subtopic, content}` - several paragraphs of original explanatory prose per subtopic, meant to be read end-to-end before self-testing) and 8 question/answer pairs spanning easy/medium/hard. The frontend renders the reading content as an always-visible card and scopes the collapsible accordion to only the practice questions, not the reading material - a deliberate split so the page reads as a genuine one-stop-shop rather than just a Q&A list. `subtopic_content` is empty for LLM-generated topics today (the agent pipeline doesn't produce reading content, only questions), and the frontend simply skips the reading card for those subtopics. In total: 7 subtopics/56 questions each for Java and Spring Boot, 6 subtopics/48 questions each for RAG and LangChain - 208 real Q&A pairs and 26 reading passages across the 4 curated topics.

`SubtopicProgress` (table `subtopicprogress`, endpoints `GET`/`POST /api/progress`) tracks a per-user "I've reviewed this subtopic" checkbox, independent of search history - this is what drives the progress bar on the generate page. It works the same way for LLM-generated topics too, since it's keyed on topic + subtopic name, not on whether the content was curated.

## Status

Day 2: full agentic RAG pipeline (plan -> generate -> dedupe/refine -> categorize) + eval + observability, working locally behind login, verified end-to-end against real Neon Postgres with both Anthropic and Google as the active `LLM_PROVIDER`. Day 3 (Render + Neon, CORS lockdown) is live. Since then: per-user search history with AI-assisted, DB-persisted topic categorization, and a 50-word cap on the topic field.
