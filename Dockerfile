# =======================================================
# Production Dockerfile for AI Digital Workforce Service
# =======================================================
FROM python:3.11-slim

# Set environment variables for Python & Timezone & HuggingFace
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Jakarta \
    PORT=5000 \
    GUNICORN_WORKERS=2 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=120 \
    HF_HOME=/app/.cache/huggingface

# Set working directory
WORKDIR /app

# Install system dependencies required for ML & doc processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    ca-certificates \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user and group for security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir gunicorn && \
    pip install --no-cache-dir -r requirements.txt

# Pre-cache HuggingFace tokenizer during build to avoid startup lag
RUN mkdir -p /app/.cache/huggingface && \
    python3 -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('BAAI/bge-m3')"

# Copy application source code from knowledge-expert
COPY knowledge-expert/ .

# Ensure log and cache directories exist with correct permissions
RUN mkdir -p /app/log /app/.cache && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose internal API port
EXPOSE 5000

# Container healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Graceful stop signal
STOPSIGNAL SIGTERM

# Default command: run Gunicorn with gthread worker class
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5000} --worker-class gthread --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-120} --graceful-timeout 30 --keep-alive 5 --access-logfile - --error-logfile - app:app"]
