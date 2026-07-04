# AI Video Factory - Quick Start

## Starting the system

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### 2. RQ Worker (background processing)
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

## API keys (.env)
```
FAL_KEY=your_key
VIDEO_API_KEY=your_key
OPENAI_API_KEY=your_key
```

## Access
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
