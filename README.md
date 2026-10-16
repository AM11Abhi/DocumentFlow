# DocumentFlow

**DocumentFlow** is a cloud-ready, asynchronous document processing and validation platform designed for high-reliability workflows (such as scholarship and academic application processing). 

The platform features an asynchronous pipeline backed by PostgreSQL and Redis, implementing the **Transactional Outbox Pattern** for guaranteed message dispatch, **distributed worker lease recovery with heartbeats**, a configurable **business rules validation engine**, and a responsive **React SPA dashboard**.

---

## Architecture & Workflow Pipeline

```text
[ Client / Browser ]
        │
        ▼ (POST /documents)
┌────────────────────────────────────────────────────────┐
│                   FastAPI REST API                     │
│  - Validate file magic bytes (PDF, JPEG, PNG) & size   │
│  - Persist original file to storage (uploads/)         │
│  - Insert Document & ProcessingJob (Atomic DB tx)      │
│  - Insert OutboxEvent (Atomic DB tx)                   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│               Transactional Outbox Dispatcher          │
│  - SELECT PENDING events FOR UPDATE SKIP LOCKED        │
│  - LPUSH job payload to Redis queue                    │
│  - Mark PUBLISHED (or FAILED with exponential backoff) │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (Redis List Queue)
┌────────────────────────────────────────────────────────┐
│             Asynchronous Python Worker                 │
│  - BRPOP job payload from Redis                        │
│  - Acquire lease (worker_id, lease_expires_at)         │
│  - Background lease heartbeat renewal thread           │
│  - Periodic crash recovery for abandoned jobs          │
│  - Text & metadata extraction (PyMuPDF / Extractor)    │
│  - Business rules validation engine                    │
│  - Persist ExtractedData & ValidationResult            │
│  - Transition Document & Job -> COMPLETED / FAILED     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (Polling GET /documents)
┌────────────────────────────────────────────────────────┐
│                 React SPA Dashboard                    │
│  - Document list with real-time status badges          │
│  - Drag-and-drop file upload zone                      │
│  - Detailed inspection (extracted fields & rule audit) │
│  - Server-side pagination & retry controls             │
└────────────────────────────────────────────────────────┘
```

---

## Core Features by Phase

- **Phase 1 — Ingestion & Storage**: FastAPI endpoints for document upload, magic byte validation (PDF, JPEG, PNG), 10 MB file size limit, and UUID-based isolated file storage.
- **Phase 2 — Asynchronous Processing**: Decoupled Redis job queue, background worker processing, attempt counters, and manual retry endpoint (`POST /documents/{id}/retry`).
- **Phase 3 — Extraction Engine**: Structured text and metadata extraction (CGPA, family income, applicant identity, transcript details) with PyMuPDF support.
- **Phase 4 — Validation Rules Engine**: Extensible business rule validator evaluating eligibility criteria (CGPA thresholds, income caps, document authenticity), producing structured `PASSED`, `FAILED`, or `NEEDS_REVIEW` reports.
- **Phase 5 — React SPA Frontend**: Modern web dashboard with document listing, upload progress, status polling, pagination, and rule audit modal.
- **Phase 6 — Reliability & Resilience**:
  - **Worker Crash Recovery**: Distributed leases with background heartbeat renewal and periodic recovery scanner claiming stale jobs via PostgreSQL `FOR UPDATE SKIP LOCKED`.
  - **Transactional Outbox Pattern**: Atomic state transitions and Redis message dispatch, ensuring zero message loss if the broker or worker restarts.
- **Phase 7 — Containerization & CI/CD**:
  - Multi-stage Dockerfiles (`python:3.11-slim` backend, multi-stage Node 20 + Nginx Alpine frontend).
  - Multi-container Docker Compose orchestration with dependency health checks and automated migrations.
  - GitHub Actions CI workflow running backend migrations/tests, frontend lint/build, and Docker verification in parallel.

---

## Prerequisites

Choose one of the following setups:

### Option A: Containerized (Recommended)
- **Docker Engine** (v24.0+) & **Docker Compose** (v2.20+)
  - On Windows/macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - On Linux: Docker Engine with the `docker-compose-plugin`

### Option B: Native Local Development
- **Python**: 3.11+
- **Node.js**: 20+ (LTS) & `npm`
- **PostgreSQL**: 15+
- **Redis**: 7+

---

## Quick Start with Docker Compose

Docker Compose runs the entire application stack (PostgreSQL, Redis, Alembic migrations, FastAPI backend, Python worker, and React frontend) with a single command.

### 1. Configure Environment Variables
Copy the root `.env.example` file to create your local `.env`:

```bash
cp .env.example .env
```

Default settings in `.env.example`:
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=documentflow
POSTGRES_HOST_PORT=5433
API_PORT=8000
FRONTEND_PORT=3000
VITE_API_BASE_URL=http://localhost:8000
```
> **Note on Ports**: PostgreSQL is mapped to host port `5433` by default to prevent port conflicts if you already have a local PostgreSQL instance running on `5432`.

### 2. Build and Start Services
Launch all containers in detached mode:

```bash
docker compose up --build -d
```

### 3. Verify Startup & Health Checks
Check container status and health:

```bash
docker compose ps
```

The startup orchestration follows a strict dependency chain:
1. `documentflow-postgres` and `documentflow-redis` initialize and pass their health checks.
2. `documentflow-migration` executes `alembic upgrade head` and exits successfully (`0`).
3. `documentflow-api` launches and waits until `/health` returns HTTP 200.
4. `documentflow-worker` and `documentflow-frontend` start once API and dependencies are healthy.

### 4. Service Logs & Teardown

```bash
# Follow live logs across all containers
docker compose logs -f

# Follow logs for a specific service
docker compose logs -f api
docker compose logs -f worker

# Gracefully stop containers
docker compose down

# Stop containers and remove persistent data volumes (clean slate)
docker compose down -v
```

---

## Application URLs

| Service / Interface | URL | Description |
|---|---|---|
| **Web Frontend** | [http://localhost:3000](http://localhost:3000) | React SPA dashboard (served via Nginx in Docker) |
| **API Interactive Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive OpenAPI documentation and test runner |
| **API ReDoc** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative OpenAPI documentation interface |
| **Backend Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | System status and active phase indicator |

---

## Native Local Development Setup

If you prefer running services directly on your host machine without Docker:

### 1. Database & In-Memory Broker Setup
Ensure PostgreSQL and Redis are running locally on their default ports:
- PostgreSQL on port `5432` with a database named `documentflow`.
- Redis on port `6379`.

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure backend environment
cp .env.example .env
# Update .env with your local PostgreSQL user and password if different

# Run database migrations
alembic upgrade head

# Start FastAPI API server (Terminal 1)
uvicorn main:app --reload --port 8000

# Start Background Worker process (Terminal 2)
python worker.py
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm ci

# Configure frontend environment (optional if using default localhost:8000)
cp .env.example .env

# Start Vite development server
npm run dev
```

The Vite dev server will be accessible at [http://localhost:5173](http://localhost:5173).

---

## Database Migrations (Alembic)

Database schemas are tracked using Alembic revisions located in `backend/alembic/versions/`.

```bash
cd backend

# Apply all pending migrations to the database
alembic upgrade head

# Roll back the latest migration
alembic downgrade -1

# Generate a new autogenerated migration after model updates
alembic revision --autogenerate -m "describe_changes_here"

# View current migration version
alembic current
```

---

## Running Automated Tests & Linting

### Backend Test Suite (Pytest)
The backend test suite includes 55 unit and integration tests covering upload validation, worker processing, text extraction, validation rules, crash recovery, lease heartbeats, and transactional outbox behavior.

> **Note**: Automated tests utilize `fakeredis` and do not require a running Redis instance.

```powershell
cd backend

# On Windows PowerShell:
$env:PYTHONPATH="."
.\venv\Scripts\pytest.exe -v

# On Linux/macOS:
export PYTHONPATH="."
pytest -v
```

### Frontend Code Quality & Production Build

```bash
cd frontend

# Run Oxlint (fast JavaScript/React linter)
npm run lint

# Compile production bundle using Vite
npm run build
```

---

## Continuous Integration (GitHub Actions)

The repository includes a GitHub Actions workflow in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) that runs automatically on every `push` and `pull_request` to the `main` branch.

The pipeline executes three independent, parallel jobs:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions CI Matrix                        │
├─────────────────────┬─────────────────────┬────────────────────────────┤
│     backend-ci      │     frontend-ci     │         docker-ci          │
├─────────────────────┼─────────────────────┼────────────────────────────┤
│ • Python 3.11       │ • Node.js 20        │ • Validate Compose config  │
│ • Postgres 15 &     │ • Lockfile verify   │   (docker compose config)  │
│   Redis 7 services  │   (npm ci)          │ • Build backend image      │
│ • Alembic upgrade   │ • Oxlint linter     │   (python:3.11-slim)       │
│ • 55 pytest tests   │ • Vite bundle build │ • Build frontend image     │
│   (clean test DB)   │                     │   (Node 20 + Nginx Alpine) │
└─────────────────────┴─────────────────────┴────────────────────────────┘
```

---

## Environment Parity Reference

| Variable | Local Native Default | Docker Compose (`.env`) | GitHub Actions CI | Description |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://...:5432/documentflow` | `postgresql+psycopg2://...:5432/documentflow` | `postgresql+psycopg2://...:5432/documentflow_test` | PostgreSQL connection string |
| `POSTGRES_HOST_PORT` | N/A (5432) | `5433` (configurable) | `5432` | Exposed host port for containerized DB |
| `REDIS_HOST` | `localhost` | `redis` (container network) | `localhost` (runner network) | Redis host address |
| `REDIS_PORT` | `6379` | `6379` | `6379` | Redis port |
| `REDIS_QUEUE_NAME` | `document_processing_queue` | `document_processing_queue` | `document_processing_queue` | Redis queue list key |
| `UPLOAD_DIR` | `uploads` | `uploads` (`/app/uploads` volume) | `uploads` | Directory for uploaded files |
| `MAX_FILE_SIZE_BYTES` | `10485760` (10 MB) | `10485760` (10 MB) | `10485760` (10 MB) | Maximum upload payload size |
| `VITE_API_BASE_URL` | `http://localhost:8000` | `http://localhost:8000` | N/A (build-time arg) | API URL resolved by browser client |
| `API_PORT` | `8000` | `8000` | N/A | Published FastAPI API host port |
| `FRONTEND_PORT` | `5173` (Vite) | `3000` (Nginx) | N/A | Published web dashboard host port |

---

## Project Directory Structure

```text
DocumentFlow/
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions 3-job CI pipeline
├── backend/
│   ├── alembic/
│   │   ├── versions/            # Database schema migration scripts (7 revisions)
│   │   └── env.py               # Alembic environment and config loader
│   ├── app/
│   │   ├── api/                 # FastAPI routes (documents, health)
│   │   ├── db/                  # Database session and base model definitions
│   │   ├── models/              # SQLAlchemy models (Document, Job, Outbox, Results)
│   │   ├── schemas/             # Pydantic schemas for request/response serialization
│   │   ├── services/            # Core business logic
│   │   │   ├── processors/      # Extraction logic (PyMuPDF document processor)
│   │   │   ├── validators/      # Business rules validation engine
│   │   │   ├── document_service.py # Document state transitions & outbox integration
│   │   │   ├── file_storage.py  # Magic bytes verification & chunked storage
│   │   │   ├── outbox.py        # Outbox event creation & Redis dispatcher loop
│   │   │   └── queue.py         # Redis queue operations
│   │   ├── config.py            # Pydantic BaseSettings configuration
│   │   └── worker.py            # Worker processing loop, heartbeats & crash recovery
│   ├── tests/                   # Pytest test suite (55 tests)
│   ├── Dockerfile               # Backend container image definition (Python 3.11-slim)
│   ├── .dockerignore            # Build context exclusions for backend image
│   ├── .env.example             # Template environment variables for local backend
│   ├── alembic.ini              # Alembic configuration
│   ├── main.py                  # FastAPI application entry point
│   ├── requirements.txt         # Backend Python dependencies
│   └── worker.py                # Standalone worker entry point
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios/Fetch API client and config
│   │   ├── components/          # Reusable UI components (UploadZone, DocumentList, etc.)
│   │   ├── App.jsx              # Main dashboard view & document detail inspector
│   │   └── main.jsx             # React DOM root entry point
│   ├── Dockerfile               # Multi-stage frontend image (Node 20 build -> Nginx Alpine)
│   ├── .dockerignore            # Build context exclusions for frontend image
│   ├── .env.example             # Template environment variables for local frontend
│   ├── nginx.conf               # Nginx reverse proxy & React SPA routing config
│   ├── package.json             # Frontend dependencies & npm scripts
│   └── vite.config.js           # Vite build configuration
├── samples/                     # Test fixtures for local and automated testing
├── .env.example                 # Template environment variables for Docker Compose
├── .gitignore                   # Git repository ignore rules
├── docker-compose.yml           # Multi-service Docker Compose orchestration specification
└── README.md                    # Project documentation
```
