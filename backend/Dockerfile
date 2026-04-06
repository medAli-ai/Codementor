FROM python:3.12-slim

# Install uv — copy binary directly from the official image, no pip install needed
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifest and lockfile first.
# This layer is cached independently from source code — if only .py files change,
# Docker reuses the installed deps layer and skips the (slow) uv sync step.
COPY pyproject.toml uv.lock ./

# Install production dependencies only into an in-project virtualenv
RUN uv sync --frozen --no-dev

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Put the venv on PATH so uvicorn/celery are callable without `uv run`
ENV PATH="/app/.venv/bin:$PATH"

# Copy application source after deps — keeps the dep cache valid on code changes
COPY . .

# Ensure the uploads directory exists at startup
RUN mkdir -p uploads

EXPOSE 8000

# Default entrypoint: FastAPI via uvicorn.
# The celery_worker service in docker-compose overrides this with its own `command:`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]