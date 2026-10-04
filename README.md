# IntelliPM

**AI-assisted project management** – like Jira/Trello with an explainable decision-support layer.

## What it does

- Type a one-line project idea → get an AI-generated plan (tasks, estimates, sprints, dependencies)
- Task-assignment recommendations based on skills, workload and past performance
- Forecast completion date, delay probability, and a 0–100 project health score
- Decision log and project Q&A (ask questions about your project)

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS v4, react-router-dom, axios, @tanstack/react-query, lucide-react |
| Backend | Python 3.11+, FastAPI + Uvicorn, Pydantic v2, SQLAlchemy 2.0 (sync) |
| Database | SQLite (dev) → PostgreSQL (production) |
| Auth | PyJWT + bcrypt |
| LLM | Groq (primary) / Gemini (fallback) via openai SDK |
| ML | scikit-learn, pandas, numpy, scipy |

## Quick start (development)

### Backend
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env    # then fill in your keys
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env    # optional, defaults to http://localhost:8000/api/v1
npm run dev
```

Then open http://localhost:5173 – you should see the health check page showing `{"status":"ok"}`.

## API

- Base URL: `http://localhost:8000/api/v1`
- Docs (Swagger): `http://localhost:8000/docs`
- Response envelope: `{"success": true, "data": ..., "message": "..."}`
- Health check: `GET /api/v1/health`

## Module progress

See [PROGRESS.md](./PROGRESS.md) for the current build status.

## Project structure

```
MajorProject/
  PROJECT_SPEC.md   PROGRESS.md   README.md   .gitignore
  backend/
    requirements.txt  .env.example
    app/
      main.py  config.py  database.py  models.py
      routers/   services/   ml/   ai/
    seed/   tests/
  frontend/
    src/
      api/   components/   pages/   context/
```
