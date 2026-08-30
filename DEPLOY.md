# Day 3 — Deploy Checklist

Tracking doc for going live: Render (backend web service + frontend static site) + the Neon Postgres already set up. Checked items are done; unchecked items are next. Items marked **[MANUAL]** need your Render account/dashboard - I can't do those from here, and I won't fill them with placeholder values.

## Phase 1 — Prep (code-side, no account needed)

- [x] Verify Angular production build output path (`dist/prep-app-ui/browser`)
- [x] `prep-app-be/render.yaml` - Blueprint definition for the backend web service (build/start commands, health check, every env var the app needs, secrets marked `sync: false` so Render prompts for them instead of storing them in git)
- [x] `prep-app-ui/render.yaml` - Blueprint definition for the static site (build command, publish path, SPA rewrite so client-side routing works on refresh)
- [x] Pin the Python runtime (`.python-version` + `PYTHON_VERSION` env var in render.yaml) to `3.10.13` - matches what's actually been tested locally, not context.md's original 3.11 aspiration
- [x] Confirm `CORS_ALLOW_ORIGINS` and `DATABASE_URL` are already env-driven (`app/config.py`) - no code change needed to lock them down per-environment
- [x] Confirm `/api/health` is public and unauthenticated (already true, built on Day 1) - this is what Render's health check will hit
- [x] Commit + push these files
- [x] **Fix real deploy failure**: first live attempt hit `Out of memory (used over 512Mi)` during startup - Chroma's default embedding function loads a local ONNX model (onnxruntime + model weights), comfortably 150-400MB, which alone blew past Render free tier's 512MB cap. Replaced it with Google's embedding API (`app/rag/embeddings.py`) - same interface, dramatically smaller memory footprint, verified live. **This makes `GOOGLE_API_KEY` required in every deploy from now on, regardless of which `LLM_PROVIDER` handles question generation** - Anthropic has no first-party embeddings endpoint, so Google is the only free API-based embedding option in this stack.

## Phase 2 — Backend goes live **[MANUAL from here]**

- [ ] Sign up at render.com (or confirm you already have an account) - free, GitHub login is fastest
- [ ] Connect your GitHub account to Render, authorize access to the `prep-app-be` repo
- [ ] In the Render dashboard: **New > Blueprint**, pick the `prep-app-be` repo. Render reads `render.yaml` automatically and shows the service it's about to create.
- [ ] When prompted for the `sync: false` env vars, paste in the **real** values (from your local `.env` - same values, this is not a new set of secrets):
  - `LLM_PROVIDER`
  - `ANTHROPIC_API_KEY` (only if `LLM_PROVIDER=1`)
  - `GOOGLE_API_KEY` (**always required** - RAG/dedup embeddings use it regardless of `LLM_PROVIDER`, see above)
  - `JWT_SECRET`
  - `OWNER_EMAIL`
  - `OWNER_PASSWORD_HASH`
  - `DATABASE_URL` (the same Neon pooled connection string)
  - `CORS_ALLOW_ORIGINS` - leave as anything for now (e.g. `http://localhost:4200`); it gets a real value in Phase 4, after the frontend exists
- [x] Deploy, wait for the build to finish
- [x] **Give me the resulting backend URL** - `https://prep-app-be.onrender.com`, confirmed live: `/api/health` returns 200, `/api/generate` with no token correctly returns 401

## Phase 3 — Point the frontend at the real backend (me, once I have the URL)

- [x] Update `prep-app-ui/src/environments/environment.ts` - replaced the `REPLACE-ME` placeholder with `https://prep-app-be.onrender.com`
- [x] Verified the production build actually embeds that URL in the compiled bundle
- [x] Commit + push

## Phase 4 — Frontend goes live **[MANUAL]**

- [x] Deployed manually (Static Site wizard, not Blueprint) - `https://prep-app-ui.onrender.com`
- [x] Fixed real deploy issue: Render's default Node (24.14.1) didn't meet Angular CLI's minimum - pinned via `.node-version`/`NODE_VERSION`/`package.json engines`, confirmed live in build logs
- [x] Fixed real deploy issue: root `/` worked but `/login`, `/generate` 404'd - manually-created static sites don't read `render.yaml`'s `routes`, so the SPA rewrite rule (`/*` -> `/index.html`, Rewrite) had to be added by hand in Settings -> Redirects/Rewrites. Verified: both routes now return 200.

## Phase 5 — Lock CORS to the real frontend origin **[MANUAL]**

- [ ] In the Render dashboard, on the **backend** service's Environment tab, set `CORS_ALLOW_ORIGINS` to `https://prep-app-ui.onrender.com` (no trailing slash)
- [ ] Save - Render redeploys the backend automatically with the new value

## Phase 6 — Verify (me, remotely, once both URLs exist)

- [ ] `curl` the live backend's `/api/health` - confirm it responds without a token
- [ ] `curl` the live backend's `/api/generate` with **no** token - confirm it's rejected (401), i.e. the public genuinely cannot hit it
- [ ] Log in as owner against the live backend, confirm a real generate call works end-to-end
- [ ] Open the live frontend URL, confirm it loads and can talk to the live backend (no CORS errors)
- [ ] You do a final check from your phone - open the frontend URL, log in, generate a topic

## Known, accepted tradeoffs (already in context.md, not new)

- **Cold start**: Render's free tier spins the backend down after 15 min idle; the next request pays a 30-60s wake-up cost, plus this app's RAG index rebuilding from the seed corpus (a handful of embedding API calls, not a local model load anymore - fast). Acceptable for personal use; a cron keep-alive ping or the $7/mo tier removes it, per context.md.
- **RAG/dedup embeddings now depend on Google's API being reachable and `GOOGLE_API_KEY` being valid**, even when `LLM_PROVIDER=1` (Anthropic) handles the actual question generation. A Google outage or bad key would break retrieval/dedup even on the Anthropic path. Acceptable tradeoff for fitting in 512MB; worth knowing if something breaks that isn't obviously "the LLM provider."
