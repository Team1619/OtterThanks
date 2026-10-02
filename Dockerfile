# ==========================================
# Stage 1: Build Frontend Assets
# ==========================================
FROM node:24-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package.json ./
RUN npm install --frozen-lockfile=false

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Python Application Runner
# ==========================================
FROM python:3.11-slim AS app-runner
WORKDIR /app

# Install system dependencies (curl for healthcheck, libpq for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend /app/backend

# Copy built frontend assets from stage 1
COPY --from=frontend-builder /build/dist /app/frontend/dist

ENV PYTHONPATH=/app \
    DATABASE_URL=postgresql+asyncpg://otter:otterpass@db:5432/otterthanks \
    STATIC_DIST_DIR=/app/frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
