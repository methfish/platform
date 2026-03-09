FROM python:3.11-slim

WORKDIR /app

# Ensure app module is importable from /app
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy everything and install dependencies
COPY . .
RUN pip install --no-cache-dir .

# Expose port
EXPOSE ${PORT:-8000}

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
