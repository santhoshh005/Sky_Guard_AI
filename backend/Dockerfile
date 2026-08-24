# SkyGuard AI Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend and ML modules
COPY backend /app/backend
COPY ml /app/ml

WORKDIR /app/backend

EXPOSE 8000

ENV PYTHONPATH=/app/backend:/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
