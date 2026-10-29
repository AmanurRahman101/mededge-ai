FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 libgl1 libxcb1 libx11-6 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/ ./backend/
RUN pip install ./backend
COPY data/samples/ ./data/samples/
COPY --from=frontend /build/frontend/dist/ ./frontend/dist/
EXPOSE 8000
CMD ["sh", "-c", "cd /app/backend && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
