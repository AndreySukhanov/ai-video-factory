# AI Video Factory

## Project

Full-stack AI video generation platform: trend discovery, script generation, video creation, review queue, YouTube publishing.

- **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python), SQLite, Redis
- **Deploy**: Docker Compose + nginx on VPS (your-domain.com)

## Rules

### Git & Releases
- Commit messages on **Russian**. No Claude Code mention, no Co-Authored-By
- For releases use `/deploy` skill — it handles git, GitHub release, investor doc, server deploy
- Release tags: semver `vX.Y.Z`

### Code
- `'use client'` on all interactive pages
- All UI text via i18n: `useLanguage()` hook, keys in `frontend/src/locales/{en,ru}.ts`
- API base URL from `NEXT_PUBLIC_API_BASE_URL` env var
- Never commit `.env`, credentials, API keys

### Docker
- **Local dev**: `docker compose -f docker-compose.local.yml up -d --build frontend backend`
- **Production**: `docker-compose.yml` (nginx + SSL). Do not run production compose locally
- Frontend has no hot-reload in Docker — rebuild required after changes

### Files to never commit
`*.tar`, `tmpclaude-*`, `*.docx`, `nul`, `Gemini_Generated_Image_*`, `node_modules/`, `.env`
