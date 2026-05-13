# ---- Stage 1: Build the Svelte frontend ----
FROM node:20 AS frontend-build
WORKDIR /app/frontend

# Install frontend deps and build
COPY birdle/package*.json ./
RUN npm ci
COPY birdle/ .
RUN npm run build

# ---- Stage 2: Build the FastAPI backend ----
FROM python:3.12-slim AS backend
WORKDIR /app

# Environment setup
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python deps
COPY birdle/src/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY birdle/src/backend/ .

# Copy built frontend into backend's static dir
COPY --from=frontend-build /app/frontend/src/frontend/dist ./static

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

