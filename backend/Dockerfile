FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install minimal system tools (curl for container health checks)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies using cached layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure default upload directory exists
RUN mkdir -p /app/uploads

# Copy application source code
COPY . .

# Expose FastAPI service port
EXPOSE 8000

# Default command starts FastAPI API server with Uvicorn.
# Can be overridden via Docker Compose / docker run (e.g. `python worker.py` or `alembic upgrade head`)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
