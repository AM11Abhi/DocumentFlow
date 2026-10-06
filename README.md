# DocumentFlow

**DocumentFlow** is a portfolio and learning project designed to build a cloud-ready document processing and validation platform. The initial target domain is scholarship and application document processing.

## Core Workflow Pipeline

```text
Upload → Store → Queue → Process → Validate → Result → Notify
```

---

## Current Technology Stack

- **Frontend**: React (bootstrapped with Vite)
- **Backend**: Python + FastAPI
- **Database**: PostgreSQL (managed via SQLAlchemy 2.x & Alembic)
- **Queue**: Redis
- **Worker**: Python background worker
- **Storage**: Local file storage

---

## Current Project Status

**Phase 2 — Asynchronous Processing Pipeline**

- `POST /documents`: Uploads document, validates magic bytes & size, saves file locally, creates `Document` and `ProcessingJob` (`QUEUED`), and enqueues job payload to Redis.
- `GET /documents/{document_id}`: Inspects document and processing job status (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`).
- `POST /documents/{document_id}/retry`: Re-queues failed jobs up to maximum 3 attempts.
- **Worker Process**: `worker.py` consumes Redis queue, updates job/document lifecycle state (`QUEUED` → `PROCESSING` → `COMPLETED` / `FAILED`), and tracks attempt counts.

---

## How to Run Locally

### 1. Database & Migrations (PostgreSQL & Alembic)

Ensure PostgreSQL is running locally on port `5432` with a database named `documentflow`. Apply Alembic schema migrations:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
alembic upgrade head
```

---

### 2. Redis Server

Ensure Redis is running locally on port `6379` (Redis is a required dependency for backend runtime and worker execution. Automated tests use `fakeredis` via pytest fixtures).

---

### 3. Backend API (FastAPI)

Launch Uvicorn server:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)
- **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 4. Background Worker Process

Start the background worker in a separate terminal window:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python worker.py
```

---

### 5. Frontend (React + Vite)

Start the Vite development server:

```bash
cd frontend
npm run dev
```

The React frontend application will be available at [http://localhost:5173](http://localhost:5173).

---

## Project Directory Structure

```text
DocumentFlow/
├── backend/
│   ├── app/
│   │   ├── api/             # API routes (upload, read, retry endpoints)
│   │   ├── db/              # Database session & Base metadata
│   │   ├── models/          # Document & ProcessingJob SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas (DocumentResponse, ProcessingJobResponse)
│   │   ├── services/        # Business logic (file storage, document service, Redis queue)
│   │   └── worker.py        # Worker loop logic & simulated processor
│   ├── alembic/             # Database migrations
│   ├── tests/               # Test suites (Phase 1 & Phase 2)
│   ├── main.py              # FastAPI application entry point
│   ├── worker.py            # Standalone worker runner script
│   ├── requirements.txt     # Python dependencies
│   └── .env                 # Local environment configuration
├── frontend/                # React Vite web application
├── docs/                    # Documentation
├── samples/                 # Sample documents for testing
├── .gitignore
└── README.md
```
