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

- `ANTHROPIC_API_KEY` - from console.anthropic.com (separate from Claude.ai / Claude Code auth).
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
  schemas/          Pydantic request/response models (auth, generate, pipeline)
  auth/             security (hash/JWT), deps (guard), routes (register/login/approve/revoke)
  llm/              Anthropic client wrapper - the only module that talks to the LLM
  rag/              seed corpus, Chroma retrieval, shared embedding/cosine-similarity helpers
  agent/            the 4 pipeline steps (plan/generate/dedupe-refine/categorize), eval, orchestration
  observability/    structured JSON logging + the RunTracker that feeds latency/token metrics
  api/routes.py     /api/health (public), /api/generate (protected)
scripts/hash_password.py   generates OWNER_PASSWORD_HASH
```

## The /api/generate pipeline (Day 2)

`POST /api/generate` runs a plain-Python agent loop, no framework:

1. **RAG retrieve** - embed the topic, pull the 4 nearest chunks from a small seed corpus (`app/rag/seed_corpus.py`) via a local Chroma collection (ephemeral, rebuilt from the seed corpus on every startup).
2. **Plan** - Claude breaks the topic into 4-6 subtopics.
3. **Generate** - Claude generates questions across those subtopics, grounded in the retrieved reference chunks. Over-generates a few extra, since dedup will remove some.
4. **Dedupe/refine** - candidate questions are embedded (same Chroma embedding function as step 1) and near-duplicates (cosine similarity > 0.88) are dropped. If that drops the count below target, one more Claude call tops it back up, explicitly told what's already covered.
5. **Categorize** - Claude normalizes category names and re-verifies each question's difficulty label across the whole set. It only returns index + labels, never question/answer text, so it can't accidentally rewrite content.
6. **Eval** - LLM-as-judge relevance score (1-5) per question, plus a cosine-similarity duplication check on the final set (flagged, not enforced - a report, not a rewrite).

Every step's latency and (for LLM calls) token usage is captured in a `RunTracker` and logged as one JSON line per step to stdout, plus a final `run_completed` summary line. That same data comes back in the API response (`eval` + `metrics`) for the Angular UI to render alongside the questions.

A failed Anthropic call (bad key, rate limit, outage) surfaces as `502` with a `{"detail": "LLM provider error: ..."}` body, not a bare `500` - the frontend distinguishes this from an app bug.

## Status

Day 2: full agentic RAG pipeline (plan -> generate -> dedupe/refine -> categorize) + eval + observability, working locally behind login. Deploy (Render + Neon, CORS lockdown, cold-start handling) is Day 3.
