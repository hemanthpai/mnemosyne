# Multi-stage build for production-ready local AI server deployment
FROM node:18 AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source and build
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim AS backend-builder

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

# Install system dependencies for local AI server
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    redis-tools \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Create app user for security
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Copy Python dependencies
COPY --from=backend-builder /root/.local /home/app/.local
ENV PATH=/home/app/.local/bin:$PATH

# Copy backend code
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/build ./frontend/build/

# Copy startup scripts and fix line endings
COPY scripts/ ./scripts/
RUN dos2unix ./scripts/*.sh 2>/dev/null || true && \
    chmod +x ./scripts/*.sh

# Create necessary directories
RUN mkdir -p logs data/uploads \
    && chown -R app:app /app

USER app

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/scripts/health-check-all.sh || exit 1

WORKDIR /app/backend

EXPOSE 8000

# Use startup script for proper initialization
# CMD ["/app/scripts/start-server.sh"]
CMD ["/bin/bash", "-c", "/app/scripts/start-server.sh"]