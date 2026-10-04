from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import router as documents_router

app = FastAPI(
    title="DocumentFlow API",
    description="Backend API for Document Processing & Validation Platform",
    version="0.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global unhandled exception safety net
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


app.include_router(documents_router)


@app.get("/")
def read_root():
    return {
        "message": "Welcome to DocumentFlow API",
        "status": "online",
        "phase": "Phase 1 — Document Ingestion",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "backend", "phase": "1"}
