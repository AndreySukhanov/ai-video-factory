# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Full-stack AI video generation platform: trend discovery, script generation, video creation, review queue, YouTube publishing.

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4
- **Backend**: FastAPI + SQLAlchemy (SQLite), Redis + RQ worker
- **Deploy**: Docker Compose + nginx on VPS (`your-domain.com`)

## Common Commands

### Local development (Docker — recommended)
```bash
docker compose -f docker-compose.local.yml up -d --build frontend backend
# Frontend: http://localhost:3000   Backend: http://localhost:8000   Docs: /docs
```
The local compose file mounts `./backend` so backend reloads on edit. Frontend has **no hot-reload** — rebuild after changes.

### Local development (without Docker)
```bash
# Backend API
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# RQ worker (background jobs) — separate terminal
cd backend && python -m app.worker

# Frontend — separate terminal
cd frontend && npm install && npm run dev
```

### Frontend
```bash
cd frontend
npm run dev      # next dev
npm run build    # next build (standalone output — see Dockerfile)
npm run lint     # eslint (uses eslint-config-next)
```

### Backend
- No test suite is wired up (`backend/app/tests/` is empty; `pytest` is in `requirements.txt` but unused).
- Schema changes: do **not** use Alembic — `backend/alembic/` is empty. Add migrations to the `_migrate_add_columns()` function in `backend/app/main.py` (it runs `ALTER TABLE` on startup; see existing pattern for guidance).

### Production compose
`docker-compose.yml` includes nginx + SSL and **fails locally** without certificates — use `docker-compose.local.yml` for local work. Never run prod compose locally.

## Architecture

### Request flow
1. Frontend page (e.g. `frontend/src/app/generate/page.tsx`) → wizard in `frontend/src/features/generate-v2/` → calls API via `frontend/src/lib/api.ts` (base URL from `NEXT_PUBLIC_API_BASE_URL`).
2. FastAPI router in `backend/app/api/v1/<resource>.py` (registered in `backend/app/main.py`).
3. Long-running jobs are enqueued onto Redis Queue (`backend/app/services/generation_service.py::enqueue_job`); the worker (`backend/app/worker.py`) calls `process_job`. If Redis is down, jobs run synchronously as a fallback.
4. Job execution invokes AI agents → video/image providers → writes results to SQLite, downloads media to `backend/static/generated/`, exposes them via `/static`.

### AI orchestrator (`backend/app/ai_orchestrator/`)
- `llm_client.py` — single LLM client, used by all agents (DeepSeek V3 via OpenRouter, OpenAI fallback).
- `agents/` — pluggable agents: `story_agent`, `episode_agent`, `shot_prompt_agent`, `story_generator`, `quality_checker`, `prompt_enhancer`, `prompt_softener`, `timestamp_prompt_builder`. They take an `LLMClient` and return structured Pydantic-shaped data.
- The pipeline composes them: trend → story → episodes → per-shot prompts → enhancement → quality check → (on moderation refusal) softener retry.

### Video & image providers (`backend/app/media/`)
- All video providers implement `video_provider_base.py`. A provider is selected at runtime based on which API keys are configured — `generation_service.py` does the priority routing (Replicate MiniMax > fal.ai Pika > Mock for the legacy single-job flow).
- New flows in `episodes.py` and frontend wizard let the user **pick the provider explicitly** (`seedance`, `laozhang`, `vertex`, `gemini`, `kling`, `minimax`, `replicate`, `veo31`, `pika`).
- Image providers: `image_provider_gemini` (Nano Banana, used for storyboard keyframes), `image_provider_flux`, `image_provider_seedream`.
- Video post-processing: `video_editor.py` (FFmpeg merge) and `video_extender.py` (extract last frame → continue → concatenate, up to 20× → 148s).

### Veo 3.1 conventions
- **ANCHOR+VARIABLE** prompt structure: shared `anchor_prompt` (style/character/setting) + per-episode `variable_prompt` (action/beat).
- **Visual prompts always English**; user-facing text (title/synopsis) stays in the user's language.
- **Dialogue uses colon syntax** `Character says: line` — never quotes (Veo renders quotes as on-screen subtitles).
- **Negative prompts are nouns only** (`text overlays, subtitles, cartoon`), never `no cartoon`.
- **Frame chaining**: episode N+1 takes last frame of N as `reference_image_url` and uses the `-fl` model variant.
- **Aspect ratios**: only 9:16 and 16:9 — frontend auto-switches if 1:1 is selected.

### Trendwatcher (`backend/app/services/trendwatcher/`)
- Adapters: `google_trends` (RSS primary, pytrends fallback), `youtube_trends` (Data API v3, 10k unit/day quota), `tiktok_trends` (RapidAPI primary, Apify fallback), `instagram_reels` (RapidAPI/Apify), plus `trend_analyzer` (LLM pattern extraction → 12 hook types and `narrative_structure`).
- Adapters initialize only if their API keys are present — missing keys silently disable the source rather than erroring.

### Database
- SQLite at `backend/sql_app.db` (and `backend/microdrama.db` is legacy).
- Models in `backend/app/models/`: `project`, `episode`, `scene`, `character`, `asset`, `job`, `trend` (incl. `StoryIdea`, `TrendSnapshot`), `schedule`, `youtube_channel`, `analytics`, `review`, `user`.
- `Base.metadata.create_all()` + `_migrate_add_columns()` run on every startup — additive only. **Do not use Alembic** in this repo.

### Frontend i18n
- Custom Context-based system (no `next-intl`): `frontend/src/contexts/LanguageContext.tsx`, dictionaries in `frontend/src/locales/{en,ru}.ts`, switcher at `frontend/src/components/LanguageSwitcher.tsx`.
- Default locale `ru`, persisted in `localStorage('locale')`. Use `t(key, params?)` with `{param}` interpolation. All user-visible strings go through `useLanguage()`.

### Static & uploads
- `/uploads` (mounted from `backend/uploads/`) — user-uploaded reference images, kept locally for backend processing.
- `/static` (mounted from `backend/static/`) — generated/merged videos and storyboard frames.
- Reference images need both a public URL (catbox, for external APIs like Seedance) and a local path (for backend storyboard). `ImageUploader.tsx` returns both; `convert_local_to_base64()` and `upload_local_to_catbox()` bridge the two.

## Conventions

### Git & releases
- Commit messages in **Russian**. No "Claude Code", no `Co-Authored-By`.
- Releases: invoke the `/deploy` skill — it handles git push, `gh release create` (Russian notes), investor `.docx` in `docs/`, and server deploy via `scp`/`plink`. Tags follow semver `vX.Y.Z`.

### Code
- `'use client'` on every interactive page.
- All UI text via `useLanguage()` — never hardcode.
- Backend reads config via `app.core.config.settings` (Pydantic Settings, loads `backend/.env`). Add new env vars there, not via `os.getenv` scattered through the code.

### Files never to commit
`.env`, `*.tar`, `tmpclaude-*`, `*.docx`, `nul`, `Gemini_Generated_Image_*`, `node_modules/`, API keys, `vertex-sa-key.json`.

## Reference docs in repo
- `README.md` — user-facing overview (in Russian) with API endpoints and env var table.
- `QUICKSTART.md` — non-Docker dev startup commands.
- `DEPLOYMENT.md` — DigitalOcean droplet bootstrap.
- `AGENTS.md` — duplicated subset of these rules; keep in sync if you change them here.
