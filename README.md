<div align="center">

# 🎬 AI Video Factory

**Полный production-pipeline для генерации виральных видео-сериалов**
*От обнаружения тренда до публикации на YouTube — за один запуск.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

</div>

---

## Что это

**AI Video Factory** — full-stack платформа, которая берёт идею (или существующий виральный TikTok) и превращает её в готовый видео-сериал с консистентным главным героем и автопостингом.

**Ключевое отличие** от Canva-style AI-генераторов:

- **Multimodal pattern extraction** — `yt-dlp` скачивает виральный ролик → `ffmpeg` вырезает 6 keyframes → Claude Opus 4.8 видит **кадры + транскрипт** и возвращает структурированный паттерн (character card, hook, story beats, CTA, app UI text). Не «угадывает по заголовку», а **видит** сам ролик.
- **Character consistency через storyboard** — Gemini Nano Banana с фиксированным seed рисует ключевые кадры → каждый эпизод берёт предыдущий кадр как `reference_image_url` для image-to-video → герой не меняется между сценами.
- **Multi-provider runtime-routing** — 9 video / image моделей с автоматическим fallback при таймаутах: Veo 3.1, Seedance 2.0 PRO, MiniMax Hailuo 02, Kling 3.0, Pika, WaveSpeed, Flux 1.1 Pro Ultra, Gemini Nano Banana, Seedream.
- **End-to-end automation** — от тренд-скана (Google Trends + YouTube Data API + TikTok scraping) до публикации в YouTube Shorts через OAuth — без человека в цикле.

---

## Возможности

| Что | Как это работает |
|---|---|
| 🎯 **Trend discovery** | Google Trends RSS + YouTube Data API + TikTok / Instagram scraping (RapidAPI / Apify); AI-анализ паттернов hook + narrative + emotion (12 типов хуков) |
| ✍️ **Multi-agent script generation** | Story Agent → Episode Agent → Shot Prompt Agent → Quality Checker → Softener — структурированный pipeline вместо одного «волшебного» промта |
| 🎨 **Storyboard keyframes** | Gemini Nano Banana с фиксированным seed → консистентный главный герой во всех эпизодах |
| 🎥 **9 video / image providers** | Runtime-routing по доступности API-ключей, automatic fallback chain, **i2v frame chaining** между эпизодами |
| 🔍 **Multimodal pattern extraction** | `yt-dlp` + 6 keyframes + Opus 4.8 vision → структурированный паттерн виральных роликов |
| 🎞 **FFmpeg merge engine** | Склейка футажей с переходами, синхронизация TTS, lip-sync, динамические субтитры из JSON |
| ✅ **VLM-based QA** | Vision-модели детектят брак (чёрные экраны, артефакты лиц, watermark) и автоматически отправляют сцены на перегенерацию |
| 📤 **YouTube auto-publish** | OAuth интеграция + автозагрузка готовых видео в YouTube Shorts |
| 🌐 **Custom i18n** | RU / EN на собственном React Context (без `next-intl`), `localStorage`-persistent |

---

## Архитектура

```
┌───────────────────────────────────────────────────────────────────┐
│                       AI Video Factory                            │
└───────────────────────────────────────────────────────────────────┘

  Frontend (Next.js 16 + React 19 + TS + Tailwind)
        │
        │  REST / SSE
        ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Backend (FastAPI + async + Pydantic)                    │
  │                                                          │
  │  ┌──────────────┐    ┌──────────────────────────────┐   │
  │  │ Trend Scout  │───▸│  AI Orchestrator             │   │
  │  │              │    │                              │   │
  │  │ Google RSS   │    │  ┌─────────┐  ┌─────────┐    │   │
  │  │ YouTube API  │    │  │  Story  │─▸│ Episode │    │   │
  │  │ TikTok scr.  │    │  │  Agent  │  │  Agent  │    │   │
  │  └──────────────┘    │  └─────────┘  └────┬────┘    │   │
  │                      │                    ▼         │   │
  │                      │  ┌─────────┐  ┌─────────┐    │   │
  │                      │  │ Quality │◂─│  Shot   │    │   │
  │                      │  │ Checker │  │ Prompt  │    │   │
  │                      │  └────┬────┘  └─────────┘    │   │
  │                      └───────┼────────────────────────┘ │
  │                              ▼                          │
  │  ┌───────────────────────────────────────────────────┐  │
  │  │  Media Layer (provider abstraction + routing)     │  │
  │  │                                                   │  │
  │  │  Video: Veo 3.1 · Seedance · MiniMax · Kling     │  │
  │  │         Pika · WaveSpeed · Vertex · Gemini       │  │
  │  │  Image: Flux · Nano Banana · Seedream            │  │
  │  │  TTS:   ElevenLabs   ASR: Whisper (self-hosted)  │  │
  │  └─────────────────────┬─────────────────────────────┘  │
  │                        ▼                                │
  │  ┌────────────────────────────────────────────────┐     │
  │  │  Post-processing: FFmpeg merge + VLM QA        │     │
  │  └────────────────────────┬───────────────────────┘     │
  │                           ▼                             │
  │  ┌────────────────────────────────────────────────┐     │
  │  │  Review queue + YouTube auto-publish (OAuth)   │     │
  │  └────────────────────────────────────────────────┘     │
  │                                                         │
  │  Job orchestration: Redis + RQ worker                   │
  │  Storage:           SQLite (SQLAlchemy)                 │
  └─────────────────────────────────────────────────────────┘
```

---

## Стек

**Backend**
Python 3.11 · FastAPI · async/asyncio · SQLAlchemy · Pydantic · Redis + RQ · SQLite

**Frontend**
Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4

**AI / ML**
Anthropic Claude (Opus / Sonnet / Haiku) · OpenAI · DeepSeek · GigaChat · YandexGPT · LangChain primitives · Whisper · multimodal vision prompts · structured outputs · function calling · RAG · Chain-of-Thought · semantic caching

**Видео / изображения**
Veo 3.1 (Vertex AI + Gemini API) · Kling 3.0 · Seedance 2.0 PRO · MiniMax Hailuo 02 · Pika · WaveSpeed · Flux 1.1 Pro Ultra · Gemini Nano Banana · Seedream · ElevenLabs (TTS)

**Media processing**
FFmpeg · ffprobe · yt-dlp · keyframe extraction · lip-sync · audio-video synchronization

**DevOps**
Docker · Docker Compose · nginx · Linux · Let's Encrypt · Google Cloud · AWS

---

## Быстрый старт

```bash
# 1) Clone
git clone https://github.com/AndreySukhanov/ai-video-factory.git
cd ai-video-factory

# 2) Add API keys
cp backend/.env.example backend/.env
# Edit backend/.env with at least:
#   OPENROUTER_API_KEY=...   # or ANTHROPIC_API_KEY / OPENAI_API_KEY
#   REPLICATE_API_TOKEN=...  # for video generation

# 3) Run
docker compose up -d --build

# Frontend → http://localhost:3000
# Backend  → http://localhost:8000
# API docs → http://localhost:8000/docs
```

**Минимум для генерации:** один LLM-ключ (OpenRouter / Anthropic / OpenAI) + один video-ключ (Replicate / Vertex / Gemini). Остальные провайдеры активируются по мере добавления ключей в `.env`.

---

## Use cases

### 1️⃣ Clone виральный TikTok с консистентным героем

```
POST /api/v1/trends/{trend_id}/clone-brief
# → multimodal extraction: yt-dlp + 6 keyframes + Opus 4.8 → структурированный brief
# → storyboard через Nano Banana с фиксированным seed → 5 keyframes
# → i2v generation (Seedance / Veo 3.1) с reference_image_url
# → FFmpeg merge → готовый видео-клон с тем же character
```

### 2️⃣ Story Mode — сериал из одной идеи

```
POST /api/v1/episodes/generate-series
{ "idea": "Детектив расследует загадочные исчезновения в прибрежном городке",
  "genre": "thriller", "episodes": 6 }
# → multi-agent: story → episode prompts → shot prompts → quality check
# → batch video generation с frame chaining
# → автоматическое объединение в один файл
```

### 3️⃣ End-to-end automation

```
GET  /api/v1/trends/discover     # сканируем тренды
POST /api/v1/episodes/generate   # генерируем видео
POST /api/v1/episodes/merge      # склеиваем
POST /api/v1/youtube/publish     # публикуем
# → trend → script → video → publish без человеческого вмешательства
```

---

## API Endpoints

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/api/v1/trends/` | Список trending тем (Google + YouTube + TikTok) |
| `POST` | `/api/v1/trends/{id}/clone-brief` | Multimodal extraction → структурированный brief |
| `POST` | `/api/v1/episodes/generate` | Генерация одного эпизода (text-to-video или image-to-video) |
| `POST` | `/api/v1/episodes/generate-series` | Multi-agent script для сериала |
| `POST` | `/api/v1/episodes/storyboard` | Keyframes через Gemini Nano Banana с фиксированным seed |
| `POST` | `/api/v1/episodes/merge` | FFmpeg merge нескольких эпизодов |
| `POST` | `/api/v1/episodes/extend` | Extend видео: extract last frame → continue → concatenate |
| `GET` | `/api/v1/review/queue` | Очередь ревью с VLM-QA-проверками |
| `GET` | `/api/v1/youtube/auth/url` | OAuth подключение YouTube канала |

Полная Swagger-документация: `http://localhost:8000/docs`

---

## Структура проекта

```
ai-video-factory/
├── frontend/                         # Next.js 16 + TS
│   └── src/
│       ├── app/                      # App Router pages (generate, trends, review, dashboard)
│       ├── features/generate-v2/     # Multi-step wizard
│       ├── contexts/                 # i18n LanguageContext
│       └── lib/api/                  # API client
│
├── backend/
│   └── app/
│       ├── api/v1/                   # FastAPI routers
│       ├── ai_orchestrator/
│       │   ├── llm_client.py         # Unified LLM client (multi-provider)
│       │   └── agents/               # Story, Episode, ShotPrompt, QualityChecker, Softener
│       ├── media/                    # Video / image / TTS providers (one base class)
│       ├── services/
│       │   ├── trendwatcher/         # Google Trends + YouTube + TikTok + pattern extractor
│       │   ├── generation_service.py # Job orchestration, fallback routing
│       │   ├── video_editor.py       # FFmpeg merge
│       │   └── video_extender.py     # Extract-last-frame → continue → concatenate
│       ├── models/                   # SQLAlchemy (project, episode, trend, ...)
│       ├── worker.py                 # RQ worker entrypoint
│       └── main.py                   # FastAPI app + startup migrations
│
└── docker-compose.yml                # Redis + Backend + Worker + Frontend
```

---

## Переменные окружения

| Переменная | Описание | Обязательна |
|------------|----------|-------------|
| `OPENROUTER_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM-провайдер (минимум один) | Да |
| `REPLICATE_API_TOKEN` | Replicate для Veo / MiniMax / Pika | Для видео |
| `GEMINI_API_KEY` | Gemini API для Veo 3.1 + Nano Banana | Опционально |
| `VERTEX_PROJECT_ID` + `vertex-sa-key.json` | Vertex AI native Veo 3.1 | Опционально |
| `LAOZHANG_API_KEY` | LaoZhang OpenAI-совместимый прокси (Claude + Seedance + Veo) | Опционально |
| `WAVESPEED_API_KEY` | WaveSpeed Seedance 2.0 | Опционально |
| `ELEVENLABS_API_KEY` | TTS озвучка | Опционально |
| `YOUTUBE_API_KEY` | YouTube Data API v3 (trend source) | Для YouTube trends |
| `APIFY_API_TOKEN` / `RAPIDAPI_KEY` | TikTok / Instagram scraping | Для соц-трендов |
| `YOUTUBE_CLIENT_ID` + `YOUTUBE_CLIENT_SECRET` + `ENCRYPTION_KEY` | OAuth подключение YouTube канала | Для auto-publish |

Полный шаблон — `backend/.env.example`.

---

## Roadmap

- [ ] **Voice cloning** — TTS под конкретного speaker по 30-сек reference
- [ ] **A/B testing of hooks** — автоматический split-тест разных вариантов первых 3 секунд
- [ ] **Music generation** — Suno / Udio integration для саундтрека эпизодов
- [ ] **Multi-platform publish** — TikTok / Reels API кроме YouTube Shorts
- [ ] **Analytics dashboard** — CTR / retention / engagement per generated series

---

## Лицензия

Проприетарное ПО. Все права защищены.

---

<div align="center">

**Made with ⚙️ Python + 🎨 Next.js + 🧠 LLM orchestration**
[GitHub](https://github.com/AndreySukhanov) · [LinkedIn](https://www.linkedin.com/in/andrei-sukhanov-2605821b9)

</div>
