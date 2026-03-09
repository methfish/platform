FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy everything first so app module is available for install
COPY . .

# Install Python dependencies (non-editable for production)
RUN pip install --no-cache-dir "."

# Expose port
EXPOSE ${PORT:-8000}

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
