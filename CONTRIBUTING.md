# Contributing to AI Video Factory

Thanks for your interest! Contributions are welcome — the architecture is deliberately plug-and-play, so most valuable additions are small and self-contained.

## Great first contributions

### 1. A new video / image / TTS provider
Providers live in `backend/app/media/`. A video provider is one class implementing `video_provider_base.py`:

```python
class MyProvider(VideoProvider):
    def generate_clip(self, visual_prompt: str, duration_sec: int,
                      aspect_ratio: str, reference_image_url: str | None = None,
                      **kwargs) -> str:
        ...  # return the video URL
```

Then register it in `get_video_provider()` (`backend/app/services/episode_generation_service.py`) and add its model id to `ALLOWED_VIDEO_MODELS` (`backend/app/schemas/episodes.py`).

### 2. A new trend source
Trend adapters live in `backend/app/services/trendwatcher/`. Subclass the base adapter, return normalized trend dicts, and initialize only when your API key is present (missing keys must disable the source silently — see existing adapters).

### 3. Niche keyword packs & UI translations
- Niche packs: `backend/app/services/trendwatcher/niches.py` (per-locale keywords/hashtags/queries).
- UI dictionaries: `frontend/src/locales/en.ts` and `ru.ts` — keys must stay in sync between both files.

## Development setup

```bash
docker compose -f docker-compose.local.yml up -d --build
# backend hot-reloads on edit (mounted volume); frontend needs a rebuild
```

Without Docker: see [QUICKSTART.md](QUICKSTART.md).

## Ground rules

- **English everywhere** — code, comments, commits, PRs. (Russian strings in `ru.ts` and `niches.py` are product data, not repo language.)
- All UI text goes through `t()` / `useLanguage()` — no hardcoded strings.
- Backend config goes through `app/core/config.py` (Pydantic Settings) — no scattered `os.getenv`.
- No Alembic — schema changes go into `_migrate_add_columns()` in `backend/app/main.py` (additive `ALTER TABLE` only).
- Run `npm run lint` and `npm run build` in `frontend/` before submitting frontend changes.

## Bigger changes

Open an issue first and describe the approach — happy to discuss architecture before you invest time.
