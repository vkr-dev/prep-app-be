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
  main.py           FastAPI app, CORS, owner bootstrap on startup
  config.py         Settings from env (.env locally, real env vars on Render)
  db.py             SQLModel engine/session (Neon Postgres)
  models/user.py    SQLModel User table
  schemas/          Pydantic request/response models (auth, generate)
  auth/             security (hash/JWT), deps (guard), routes (register/login/approve/revoke)
  llm/              Anthropic client wrapper - the only module that talks to the LLM
  api/routes.py     /api/health (public), /api/generate (protected)
scripts/hash_password.py   generates OWNER_PASSWORD_HASH
```

## Status

Day 1 walking skeleton: auth + one structured Anthropic call, working locally. RAG, the four-step agent loop, eval, and observability are Day 2.
