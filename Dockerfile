# ============================================================================
# SplitLang Multi-Stage Production Dockerfile (React 19 + FastAPI + ANTLR4)
# Security: non-root runtime user, minimal slim base, zero baked secrets
# ============================================================================

# Stage 1: Build React + Vite Frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: Minimal Python Runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Create unprivileged non-root system user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy enterprise layered backend, ANTLR generated files, demo scripts, and built React SPA
COPY backend ./backend
COPY examples ./examples
COPY main.py cli.py ./
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "backend.app:get_default_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
