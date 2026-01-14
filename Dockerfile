# certbot-aliyun: Automated Let's Encrypt certificate management for Alibaba Cloud
# Single-stage Docker build

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    certbot \
    python3-certbot-dns-route53 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv
RUN --mount=type=cache,mode=0777,target=/app/.uv-cache UV_HTTP_TIMEOUT=6000 uv sync --cache-dir=/app/.uv-cache

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash certbot && \
    mkdir -p /app /certs /certbot-config && \
    chown -R certbot:certbot /app /certs /certbot-config

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

# Default command (run cron)
CMD ["uv", "run", "python", "-m", "auto_cert.cron"]