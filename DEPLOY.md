# Day 3 — Deploy Checklist

Tracking doc for going live: Render (backend web service + frontend static site) + the Neon Postgres already set up. Checked items are done; unchecked items are next. Items marked **[MANUAL]** need your Render account/dashboard - I can't do those from here, and I won't fill them with placeholder values.

## Phase 1 — Prep (code-side, no account needed)

- [x] Verify Angular production build output path (`dist/prep-app-ui/browser`)
- [x] `prep-app-be/render.yaml` - Blueprint definition for the backend web service (build/start commands, health check, every env var the app needs, secrets marked `sync: false` so Render prompts for them instead of storing them in git)
- [x] `prep-app-ui/render.yaml` - Blueprint definition for the static site (build command, publish path, SPA rewrite so client-side routing works on refresh)
- [x] Pin the Python runtime (`.python-version` + `PYTHON_VERSION` env var in render.yaml) to `3.10.13` - matches what's actually been tested locally, not context.md's original 3.11 aspiration
- [x] Confirm `CORS_ALLOW_ORIGINS` and `DATABASE_URL` are already env-driven (`app/config.py`) - no code change needed to lock them down per-environment
- [x] Confirm `/api/health` is public and unauthenticated (already true, built on Day 1) - this is what Render's health check will hit
- [ ] Commit + push these files

## Phase 2 — Backend goes live **[MANUAL from here]**

- [ ] Sign up at render.com (or confirm you already have an account) - free, GitHub login is fastest
- [ ] Connect your GitHub account to Render, authorize access to the `prep-app-be` repo
- [ ] In the Render dashboard: **New > Blueprint**, pick the `prep-app-be` repo. Render reads `render.yaml` automatically and shows the service it's about to create.
- [ ] When prompted for the `sync: false` env vars, paste in the **real** values (from your local `.env` - same values, this is not a new set of secrets):
  - `LLM_PROVIDER`
  - `ANTHROPIC_API_KEY`
  - `GOOGLE_API_KEY`
  - `JWT_SECRET`
  - `OWNER_EMAIL`
  - `OWNER_PASSWORD_HASH`
  - `DATABASE_URL` (the same Neon pooled connection string)
  - `CORS_ALLOW_ORIGINS` - leave as anything for now (e.g. `http://localhost:4200`); it gets a real value in Phase 4, after the frontend exists
- [ ] Deploy, wait for the build to finish
- [ ] **Give me the resulting backend URL** (looks like `https://prep-app-be-xxxx.onrender.com`)

## Phase 3 — Point the frontend at the real backend (me, once I have the URL)

- [ ] Update `prep-app-ui/src/environments/environment.ts` - replace the `REPLACE-ME` placeholder with the real backend URL
- [ ] Commit + push

## Phase 4 — Frontend goes live **[MANUAL]**

- [ ] In the Render dashboard: **New > Blueprint**, pick the `prep-app-ui` repo
- [ ] Deploy, wait for the build to finish
- [ ] **Give me the resulting frontend URL** (looks like `https://prep-app-ui-xxxx.onrender.com`)

## Phase 5 — Lock CORS to the real frontend origin **[MANUAL]**

- [ ] In the Render dashboard, on the **backend** service's Environment tab, set `CORS_ALLOW_ORIGINS` to the exact frontend URL from Phase 4 (no trailing slash)
- [ ] Save - Render redeploys the backend automatically with the new value

## Phase 6 — Verify (me, remotely, once both URLs exist)

- [ ] `curl` the live backend's `/api/health` - confirm it responds without a token
- [ ] `curl` the live backend's `/api/generate` with **no** token - confirm it's rejected (401), i.e. the public genuinely cannot hit it
- [ ] Log in as owner against the live backend, confirm a real generate call works end-to-end
- [ ] Open the live frontend URL, confirm it loads and can talk to the live backend (no CORS errors)
- [ ] You do a final check from your phone - open the frontend URL, log in, generate a topic

## Known, accepted tradeoffs (already in context.md, not new)

- **Cold start**: Render's free tier spins the backend down after 15 min idle; the next request pays a 30-60s wake-up cost. On top of that, this app's RAG index rebuilds from the seed corpus on every startup, and Chroma's embedding model downloads (~80MB) on a fresh container if it's not already cached in the container's filesystem - so a genuinely cold start could take noticeably longer than a typical Render free-tier wake-up. Acceptable for personal use; a cron keep-alive ping or the $7/mo tier removes it, per context.md.
- **No persistent disk on the free web service** - each fresh deploy/restart re-downloads the Chroma embedding model. Doesn't affect correctness, just adds to cold-start time.
