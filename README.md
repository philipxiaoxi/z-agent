# zspace-agent

NAS Agent — React frontend + FastAPI backend.

## Quick Start

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173`, proxies `/api` to backend at `http://localhost:8000`.
