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
- **Database (Planned)**: PostgreSQL
- **Queue (Planned)**: Redis
- **Workers (Planned)**: Python background workers
- **Storage**: Local file storage (evolving to cloud storage)

---

## Current Project Status

**Phase 0 — Project Setup**

- Project repository structure initialized
- Minimal Python + FastAPI backend setup with health checks
- Minimal React frontend (Vite-powered) setup
- Initial document sample folders created (`marksheet`, `income_certificate`, `identity`)

---

## How to Run Locally

### 1. Backend (FastAPI)

Navigate to the `backend` directory, activate the virtual environment, and launch Uvicorn:

#### Windows (PowerShell):
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

#### macOS / Linux:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

The backend API will be available at:
- API Base / Health: [http://localhost:8000/health](http://localhost:8000/health)
- Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 2. Frontend (React + Vite)

Navigate to the `frontend` directory and start the Vite development server:

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
│   ├── main.py              # FastAPI application entry point & health endpoints
│   ├── requirements.txt     # Python dependencies
│   └── venv/                # Local virtual environment
├── frontend/
│   ├── src/                 # React component source code
│   ├── package.json         # Node.js dependencies and scripts
│   └── vite.config.js       # Vite configuration
├── docs/                    # Project documentation
├── samples/                 # Sample test documents
│   ├── marksheet/           # Academic transcripts & marksheets
│   ├── income_certificate/  # Income certificates
│   └── identity/            # Synthetic identity documents
├── .gitignore               # Git ignore rules
└── README.md                # Project documentation & setup instructions
```
