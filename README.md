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

Guest flow: `POST /api/auth/register` -> owner calls `POST /api/auth/approve/{user_id}` (1-hour window starts now) -> guest's existing token starts passing the guard. `POST /api/auth/revoke/{user_id}` cuts it off immediately. `GET /api/auth/users` lists every non-owner account (pending/approved/revoked) - this is what the frontend's `/admin` page (owner-only, see prep-app-ui's README) is actually built on, so approving a guest is a click in the UI rather than a manual API call. The 1-hour window is enforced by timestamp on every single protected request via `get_current_user()`, not just checked at login - access dies mid-session the instant `access_expires_at` passes, whether or not the user does anything to trigger it.

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
6. **Explain** (`explain_subtopics()`) - runs against the FINAL, post-categorize subtopic names (not the plan step's initial guess), so every entry's key matches a real question category. Writes a short explanatory passage per subtopic, grounded in the same reference chunks as generation - this is what makes an LLM-backed search render exactly like a curated one on the frontend: reading content first, practice questions in the accordion after, never just an isolated Q&A list. Degrades to an empty list (never fails the request) if this one call has a bad day - a search should still return its questions even without the writeup that one time.
7. **Eval** - LLM-as-judge relevance score (1-5) per question, plus a cosine-similarity duplication check on the final set (flagged, not enforced - a report, not a rewrite).

"The LLM" is whichever provider `LLM_PROVIDER` selects (`app/llm/client.py`) - every step calls `call_structured()` and never imports a provider SDK directly, so this list holds regardless of which one is active.

Every step's latency and (for LLM calls) token usage is captured in a `RunTracker` and logged as one JSON line per step to stdout, plus a final `run_completed` summary line. That same data comes back in the API response (`eval` + `metrics`) for the Angular UI to render alongside the questions.

A failed provider call (bad key, rate limit, outage) surfaces as `502` with a `{"detail": "LLM provider error: ..."}` body; a response that came back but never parsed into the expected schema (safety refusal/block, or malformed JSON that survived one retry) surfaces as `502` with `{"detail": "LLM output error: ..."}`. Either way, not a bare `500` - the frontend distinguishes provider failures from an app bug.

## Shared topic cache

`POST /api/generate` checks a Postgres-backed cache (`app/agent/cache.py`, table `questionsetcache`) before running the pipeline at all. The cache key is the topic normalized (lowercased, whitespace-collapsed) - **not** per-user. The first person to ask about "SQL" pays for the full pipeline run; every later request for "SQL" (or "sql", or "  SQL  " - any user, including a different one) is served straight from the DB, with `from_cache: true` and zero token usage in the response. This is exact-match only, not embedding-similarity matching - "SQL" and "SQL joins" are different cache entries by design.

There's no cache invalidation yet - an entry lives forever until manually deleted from the table. Fine for now; a "regenerate" bypass is an easy follow-up if question sets need to be refreshed later.

## Input safety guardrail

`POST /api/generate`'s `topic` field is the only free-text user input anywhere in this app, so it's the one thing that needs a content guardrail before it reaches the pipeline (`app/safety.py`, `check_topic_safety()`). Two layers, defense in depth: a fast, zero-cost keyword pre-check catches blatant explicit-content requests with no LLM call at all, and an LLM classification call catches subtler attempts - indirect phrasing, or a prompt trying to get the model to ignore its instructions and produce something unrelated to legitimate interview prep. Either layer rejects before `record_search()` or the pipeline ever runs - a rejected topic is never saved to search history, never cached, and never spends a real generation call.

The check runs on a **cache miss only** - deliberately, not on every request. A cache hit (curated content or a prior real pipeline run) already either was hand-authored or already passed this exact check the first time it was ever generated, so there's nothing to re-check. This matters beyond avoiding a redundant call: the classifier fails **closed** (a check that couldn't run is treated as a rejection, not a pass - the one step in this app that doesn't degrade gracefully on an LLM failure), so running it unconditionally on every request would mean a transient classifier hiccup could intermittently reject even a previously-safe, already-cached topic. Confirmed live this was a real regression, not hypothetical: with Groq (the current default `LLM_PROVIDER`) actively misbehaving on structured output, checking on every request broke previously-working, already-cached searches. Moving the cache lookup ahead of the safety check removes that exposure from the common path entirely, without weakening the guarantee - every topic that ever reaches the pipeline for the first time still goes through it.

The classifier call itself deliberately bypasses `app.llm.client`'s swappable `LLM_PROVIDER` selector and always calls Google directly (`app/llm/google_client.py`), never Anthropic (real per-token cost, avoided on purpose) and never Groq. Confirmed live: Groq's `qwen3.6-27b` consistently - not intermittently - failed to produce valid structured output for this specific classification prompt, a 100% failure rate that, combined with fail-closed, meant every single new topic search was being rejected while `LLM_PROVIDER=3` was active, regardless of the topic's actual content. Google is already a hard, unconditional dependency of this app for embeddings regardless of `LLM_PROVIDER` (see below), so routing this one small, cheap call (`max_tokens=200`) through it too doesn't add a new dependency, just reuses one that's already required.

Also found and fixed live while building this: Groq's strict JSON-schema mode requires every property to appear in a schema's `required` array, with no concept of "optional with a Python-side default" - `TopicSafetyResult`'s `reason` field (which defaults to an empty string) tripped this immediately. `app/llm/groq_client.py` now recursively forces every property into `required` for any schema sent to Groq, alongside its existing `additionalProperties: false` fixup, so a future schema with a defaulted field doesn't hit the same wall.

This is the one LLM-dependent step in the whole app that fails **closed**, not open - every other step (RAG retrieval, dedupe, topic labeling, the explain step) degrades gracefully to a safe default if its LLM call fails, since a missed enhancement is an acceptable availability tradeoff. A safety check that couldn't run is not the same as one that passed, so a classifier failure here is treated as a rejection too, not silently skipped.

The user-facing rejection is a deliberately terse, uniform `400` with body `{"detail": "NO"}` - identical regardless of which layer caught it or why, on purpose: not revealing the reason is itself part of the guardrail, since it gives nothing away that would help someone iterate their way past it. The real reason (keyword match, classifier's stated reason, or the underlying provider error) is still captured server-side via structured `log_event()` calls for the owner's own visibility.

## Per-user search history + AI topic categorization

`POST /api/generate` also records the search into `GET /api/search-history` (`app/history/service.py`) - unlike the question cache, this table (`searchhistory`) is per-user, since it's each user's own list of past searches. Re-searching a topic bumps its timestamp rather than duplicating it.

Every topic also gets a short label + category (`table topiclabel`) - **shared** across all users, same normalized-topic-key pattern as the question cache. The LLM is only called to assign a label the *first time anyone ever searches a topic*; every later search of it (any user) reuses the stored row. When a genuinely new topic does need labeling, the LLM is shown every existing category already in the table and told to reuse one if it fits (matched by meaning, not exact wording) - this is what makes "Java Streams" and "Java Generics" land in the same "Java" group instead of each inventing a slightly different category name.

`GenerateRequest.topic` is capped at 50 words (`app/schemas/generate.py`), enforced both server-side (a Pydantic validator) and client-side (the search page disables submit past the limit).

## Curated content (no LLM) + subtopic progress tracking

`scripts/seed_curated_topics.py` inserts hand-authored, comprehensive content directly into the DB for a set of curated topics - no LLM call anywhere in that script. It reuses the exact same tables as LLM-generated content (`save_to_cache`, `TopicLabel`, `SearchHistory`), so these topics are just instant, zero-token cache hits from the moment the script runs. `GenerateResult.curated: true` marks these as never having run the pipeline at all (distinct from `from_cache`, which just means "not paid for on this particular request") - it's not surfaced as a UI badge, since the content itself is indistinguishable in shape and quality from a real pipeline run; the field exists for internal/observability purposes only. Safe to re-run - every insert is an upsert. Java and Spring Boot share the `"Java"` category; RAG, LangChain, and Generative AI & LLM Fundamentals share `"AI/LLM"`; System Design has its own `"System Design"` category - topics sharing a category group together on the search page exactly like same-topic LLM-categorized searches would.

Each curated topic is organized into subtopics (the `Question.category` field doubles as the subtopic name), each with two parts: real reading content (`GenerateResult.subtopic_content`, a `SubtopicContent` list of `{subtopic, content}` - several paragraphs of explanatory prose per subtopic, meant to be read end-to-end before self-testing) and question/answer pairs (8 per subtopic, spanning easy/medium/hard). The frontend renders the reading content as an always-visible card and scopes the collapsible accordion to only the practice questions, not the reading material - a deliberate split so the page reads as a genuine one-stop-shop rather than just a Q&A list. An LLM-backed (non-curated) search populates `subtopic_content` too, via the pipeline's own **Explain** step (see below) - so a fresh, uncached search looks and reads identically to a curated one, not a lesser Q&A-only experience. The frontend skips the reading card only in the rare case a subtopic genuinely has no matching entry (an older cached result from before the Explain step existed, or a run where that one step failed and degraded to an empty list).

Subtopic coverage is deliberately broad per topic, not a handful of headline areas - per explicit direction, the goal is that a topic's page covers its subject end-to-end with no gaps, not a sampler. Currently seeded:

- **Java** - 14 subtopics (112 questions): core OOP, collections, concurrency, exceptions, streams, memory/JVM, generics, I/O & NIO, serialization, design patterns, annotations & reflection, modern language features (records/sealed classes/pattern matching), enums & nested classes, date/time & regex, and JDBC.
- **Spring Boot** - 13 subtopics (104 questions): the original core/DI/MVC/JPA/security/config/testing set, plus AOP, caching, async/scheduling/events, Actuator/observability, microservices/Spring Cloud, and **Spring AI** (Spring's own GenAI integration framework - ChatClient, VectorStore, Advisors, function calling).
- **RAG** - 10 subtopics (80 questions): the core pipeline plus advanced patterns (Self-RAG/CRAG/GraphRAG), prompt engineering, production scaling/cost, and security/privacy.
- **LangChain** - 10 subtopics (80 questions): the core framework plus LangGraph/multi-agent orchestration, output parsing, tracing/LangSmith, and deployment.
- **Generative AI & LLM Fundamentals** (new topic) - 8 subtopics (64 questions): transformer architecture & attention, tokenization, pretraining/fine-tuning/RLHF, prompting techniques, model evaluation/alignment, inference/serving/cost optimization, AI agents & tool use, and the Model Context Protocol (MCP) - the foundational AI concepts underlying RAG/LangChain/Spring AI, not tied to any one framework.
- **System Design** - 10 subtopics (81 questions): scalability, networking/communication patterns, database design/scaling, caching, CAP theorem/consistency, distributed systems fundamentals, reliability/fault tolerance, security at scale, observability at scale, and the sequential "Designing an AI-Powered System, Step by Step" framework walkthrough.
- **AI & Agentic Engineering** - 14 subtopics (112 questions), one per named skill in a specific resume-style AI/agentic skill set, with nothing left out: agentic & multi-agent pipeline design, RAG architecture, retrieval engineering (chunking & embeddings), semantic search & re-ranking, vector stores & Chroma, LLM integration across Anthropic/Google/Groq, the multi-provider LLM abstraction, streaming responses, prompt engineering, LLM evaluation (LLM-as-judge & deduplication), AI guardrails & safety, LLMOps & observability, GitHub Copilot, and Cursor. Written to be self-contained, and several subtopics ground their content directly in this project's own real implementation and real bugs found along the way, not just general theory.
- **Six standalone system-design case-study topics** - each its own top-level searchable topic (not a subtopic buried inside "System Design"), so each shows up as its own separate home-screen search button, titled `System Design: <the system>`. Every one has the same internal shape - 5 subtopics, 40 questions - specifically built to carry a full one-hour interview: **Requirements, Scale Estimation & High-Level Architecture** → 1-2 **deep-dive** subtopics on the system's hardest technical problem → a **reliability/security/observability** subtopic → a final **Critique & Follow-Up Interview Questions** subtopic. Every case study's deep-dive content is narrated via Situation-Task-Action-Result purely as a case-study storytelling structure - explicitly noted in the content itself as distinct from STAR's actual role in behavioral interviews, and distinct from the real system-design framework covered in the standalone "Designing an AI-Powered System, Step by Step" subtopic above. Every follow-up question in the critique subtopic is tagged with a bracketed label naming exactly what it's grilling (e.g. `[Loan Limit Consistency]`, `[CAP Tradeoff]`, `[Prompt Refinement]`), so the specific concern being tested is always clear at a glance:
  - **System Design: Buy-Now-Pay-Later Payment Platform** - ledger consistency and loan-limit enforcement, installment scheduling/collections, fraud and regulatory compliance.
  - **System Design: Ride-Sharing Dispatch System** - geospatial indexing and real-time matching, surge pricing and ride lifecycle, fault isolation and abuse prevention.
  - **System Design: AI-Powered Code Review Agent** - codebase retrieval and the agentic review pipeline, noise control/confidence/cost management, security and evaluation.
  - **System Design: AI-Powered Real-Time Fraud Detection System** - tiered rules/ML/precomputed-feature scoring, where AI fits (offline pattern analysis, deliberately kept off the real-time path), explainability and observability. Deliberately cross-references the BNPL case study, since both plug into the same hypothetical payments business.
  - **System Design: Windows Notification System** - models an AI-assisted-interview format where the candidate is expected to use an AI assistant as a design collaborator, evaluated on how prompts were framed, refined after a weak first answer, and critically evaluated rather than accepted. A dedicated subtopic ("Using AI as a Design Partner") narrates the actual prompting/refinement/critique sequence step by step, and its questions include prompting-technique and AI-output-evaluation angles alongside standard per-app isolation/prioritization grilling.
  - **System Design: Proximity Search System for Food Delivery** - geohashing, the boundary/precision tradeoffs, combined filtering/caching/data freshness; models an interview with multiple design follow-ups ending in an actual coding exercise - its final subtopic includes a real coding problem (implementing Haversine-based radius filtering) with a working Python solution as the answer, not just a discussion question.

In total: 13 curated topics, 109 subtopics, 873 real Q&A pairs, and 109 reading passages.

`SubtopicProgress` (table `subtopicprogress`, endpoints `GET`/`POST /api/progress`) tracks a per-user "I've reviewed this subtopic" checkbox, independent of search history - this is what drives the progress bar on the generate page. It works the same way for LLM-generated topics too, since it's keyed on topic + subtopic name, not on whether the content was curated.

## Status

Day 2: full agentic RAG pipeline (plan -> generate -> dedupe/refine -> categorize) + eval + observability, working locally behind login, verified end-to-end against real Neon Postgres with both Anthropic and Google as the active `LLM_PROVIDER`. Day 3 (Render + Neon, CORS lockdown) is live. Since then: per-user search history with AI-assisted, DB-persisted topic categorization, and a 50-word cap on the topic field.
