# AI Video Factory

AI-платформа для автоматической генерации коротких видео-сериалов из текстовых описаний. Создавайте мини-драмы для TikTok, Reels и Shorts за минуты.

## Возможности

- **Story Mode** — Генерация многосерийных историй из одной идеи
- **Multi-Agent AI** — Story Generator, Quality Checker, Prompt Enhancer работают вместе
- **Консистентность персонажей** — Сохранение визуальной идентичности через reference-изображения
- **Безопасная модерация** — Автоматическая замена проблемных слов
- **Объединение видео** — Склейка эпизодов в один файл
- **10+ жанров** — Драма, комедия, триллер, фэнтези, романтика, экшн, хоррор, сай-фай

## Технологии

**Frontend:**

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS

**Backend:**

- Python 3.11
- FastAPI
- SQLAlchemy
- Redis + RQ

**AI-сервисы:**

- DeepSeek V3 через OpenRouter (LLM)
- Google Veo 3 через Replicate (генерация видео)

**Инфраструктура:**

- Docker & Docker Compose
- FFmpeg для обработки видео

## Быстрый старт

### Требования

- Docker & Docker Compose
- API-ключи OpenRouter и Replicate

### Установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/AndreySukhanov/ai-video-factory.git
cd ai-video-factory
```

2. Создайте файл окружения:

```bash
cp .env.example .env
```

3. Добавьте API-ключи в `.env`:

```env
OPENROUTER_API_KEY=ваш_openrouter_ключ
REPLICATE_API_TOKEN=ваш_replicate_токен
```

4. Запустите приложение:

```bash
docker-compose up -d
```

5. Откройте <http://localhost:3000>

## Использование

### Режим одиночного эпизода

1. Введите текстовое описание видео
2. Опционально загрузите reference-изображение
3. Нажмите "Generate" и подождите 2-3 минуты

### Режим Story Mode

1. Переключитесь на вкладку "Story Mode"
2. Введите идею истории (например, "Детектив расследует загадочные исчезновения в прибрежном городке")
3. Выберите жанр и количество эпизодов
4. Нажмите "Generate Episode Prompts" — AI создаст промты
5. Отредактируйте промты при необходимости
6. Нажмите "Generate All Videos" для создания серии
7. Используйте "Merge & Download" для склейки

## Структура проекта

```
ai-video-factory/
├── frontend/               # Next.js фронтенд
│   └── src/app/           # Страницы и компоненты
├── backend/               # FastAPI бэкенд
│   └── app/
│       ├── api/           # REST endpoints
│       ├── ai_orchestrator/  # AI-агенты
│       │   └── agents/    # Story Generator, Quality Checker
│       ├── media/         # Провайдеры видео
│       └── core/          # Конфигурация
├── docker-compose.yml     # Оркестрация контейнеров
└── README.md
```

## Архитектура AI-агентов

```
┌─────────────────────────────────────────────────────────┐
│                   AI Video Factory                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   │
│  │   Story     │──▸│  Quality    │──▸│   Prompt    │   │
│  │  Generator  │   │   Checker   │   │  Enhancer   │   │
│  └─────────────┘   └─────────────┘   └──────┬──────┘   │
│                                              │          │
│                                              ▼          │
│                                    ┌─────────────────┐  │
│                                    │ Video Generator │  │
│                                    │  (Google Veo 3) │  │
│                                    └─────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Переменные окружения

| Переменная | Описание | Обязательна |
|------------|----------|-------------|
| `OPENROUTER_API_KEY` | API-ключ OpenRouter для LLM | Да |
| `REPLICATE_API_TOKEN` | Токен Replicate для Veo 3 | Да |
| `OPENAI_API_KEY` | API-ключ OpenAI (альтернатива) | Нет |

## API Endpoints

- `POST /api/v1/episodes/generate` — Генерация одного видео
- `POST /api/v1/story/generate` — Генерация промтов истории
- `POST /api/v1/episodes/merge` — Объединение видео
- `POST /api/v1/episodes/upload-image` — Загрузка reference-изображения

## Лицензия

Проприетарное ПО. Все права защищены.

## Автор

Андрей Суханов — AI-инженер и Full-Stack разработчик

---

*Создано для контент-креаторов*
