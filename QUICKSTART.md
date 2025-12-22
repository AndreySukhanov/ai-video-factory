# AI Video Factory - Quick Start

## Запуск системы

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### 2. RQ Worker (фоновая обработка)
```bash
cd backend
python -m rq worker --with-scheduler
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

## API ключи (.env)
```
FAL_KEY=ваш_ключ
VIDEO_API_KEY=ваш_ключ
OPENAI_API_KEY=ваш_ключ
```

## Доступ
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
