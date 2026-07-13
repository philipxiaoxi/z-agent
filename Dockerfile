# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build backend
FROM python:3.11-slim
WORKDIR /app
COPY backend/ ./
COPY --from=frontend /build/backend/static ./static
RUN pip install uv z-cli --no-cache-dir && uv sync --no-dev --no-cache
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
