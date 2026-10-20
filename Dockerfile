FROM python:3.13-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install node
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Build Frontend
WORKDIR /app
COPY src/web/package*.json ./src/web/
RUN cd src/web && npm install
COPY src/web/ ./src/web/
RUN cd src/web && npm run build

# Final Image
FROM python:3.13-slim

WORKDIR /app

# Install Poetry deps (no dev deps in production)
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi

COPY src/ ./src/
COPY --from=builder /app/src/web/dist/ ./src/api/static/

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
