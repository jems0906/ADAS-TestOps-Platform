# ADAS TestOps Platform

Operational web app for ADAS validation teams to plan test sessions, manage vehicle configs, review logger health, and index captured data files.

The platform supports full validation flow: test plans, test runs, dedicated test case library, per-run case execution results, issue tracking, and log capture indexing.

## Stack

- Frontend: React runtime (static delivery via FastAPI)
- Backend: FastAPI
- Database: PostgreSQL in production, SQLite fallback for local development
- File storage: local upload references with indexed metadata

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

The app is served as a static React runtime from `frontend/public` and does not require a Vite build.

Open the backend at `http://localhost:8000` after starting Uvicorn; it serves the UI and the API together.

## Railway deployment

Use the repository `Dockerfile` as the web service image. The backend serves the static React UI from `/` and exposes the API under `/api`.

### Services to create

1. One Railway Web Service from this repository.
2. One Railway PostgreSQL database service.

### Required environment variables

- `DATABASE_URL` (provided automatically after linking PostgreSQL)
- `APP_NAME` (optional, defaults to `ADAS TestOps Platform`)
- `UPLOAD_DIR` (optional, defaults to `/app/backend/uploads` in container)

### Deploy flow

1. Create a new Railway project.
2. Add PostgreSQL service.
3. Add a Web Service from this repo.
4. Ensure `DATABASE_URL` from PostgreSQL is shared to the Web Service.
5. Deploy. Health endpoint is available at `/api/health`.