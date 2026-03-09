FROM python:3.11-slim

WORKDIR /app

# Ensure app module is importable
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly (not as a package)
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.109.0" \
    "uvicorn[standard]>=0.27.0" \
    "gunicorn>=21.2.0" \
    "pydantic>=2.6.0" \
    "pydantic-settings>=2.1.0" \
    "sqlalchemy[asyncio]>=2.0.25" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0" \
    "redis[hiredis]>=5.0.0" \
    "aiohttp>=3.9.0" \
    "websockets>=12.0" \
    "structlog>=24.1.0" \
    "python-jose[cryptography]>=3.3.0" \
    "passlib[bcrypt]>=1.7.4" \
    "bcrypt>=4.0.0,<5.0.0" \
    "python-multipart>=0.0.6" \
    "httpx>=0.26.0" \
    "orjson>=3.9.0" \
    "prometheus-client>=0.20.0" \
    "email-validator>=2.0.0" \
    "yfinance>=0.2.36" \
    "anthropic>=0.39.0"

# Copy application code
COPY . .

# Expose port
EXPOSE ${PORT:-8000}

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
