# certbot-aliyun: Automated Let's Encrypt certificate management for Alibaba Cloud
# Multi-stage Docker build for optimized image size

# Stage 1: Builder stage for Python dependencies
FROM python:3.11-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv
RUN uv pip install --no-cache-dir -e .

# Stage 2: Runtime stage
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    certbot \
    python3-certbot-dns-route53 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash certbot && \
    mkdir -p /app /certs /certbot-config && \
    chown -R certbot:certbot /app /certs /certbot-config

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=certbot:certbot auto_cert ./auto_cert/
COPY --chown=certbot:certbot pyproject.toml ./

# Make hook script executable
RUN chmod +x /app/auto_cert/alidns_hook.py

# Set environment variables
ENV PYTHONPATH="/app"
ENV CERT_STORAGE_PATH="/app/certs"
ENV CERTBOT_CONFIG_DIR="/app/certbot-config"
ENV TZ=Asia/Shanghai

# Switch to non-root user
USER certbot

# Create necessary directories
RUN mkdir -p /app/certs /app/certbot-config

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD /bin/bash -c "python -c 'import auto_cert' && command -v certbot >/dev/null 2>&1" || exit 1

# Default command (show help)
CMD ["help"]