# CodeMentor

A personal AI coding tutor. Upload your programming textbooks and get 
RAG-enhanced answers powered by a local LLM.

## Tech Stack

**Backend:** FastAPI, PostgreSQL, Redis, Celery, Qdrant, Ollama (qwen2.5-coder:7b), BAAI/bge-small-en-v1.5  
**Frontend:** React, Vite, TailwindCSS  
**Infra:** Docker Compose, Nginx, GitHub Actions CI, NVIDIA GPU support

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.12, Node.js 20
- [uv](https://github.com/astral-sh/uv)
- NVIDIA GPU + Container Toolkit (for LLM inference)

### Installation

```bash
git clone https://github.com/medAli-ai/codementor.git
cd codementor
git checkout dev
```

### Setup environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```bash
# Database
DATABASE_URL=postgresql://codementor_user:yourpassword@localhost:5433/codementor

# JWT
SECRET_KEY=your_secret_key

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=codementor_rag

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Embeddings
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DEVICE=cpu

# Superadmin (optional)
DEFAULT_SUPERADMIN_EMAIL=
DEFAULT_SUPERADMIN_USERNAME=
DEFAULT_SUPERADMIN_PASSWORD=
```

## Development

Start infrastructure (Postgres, Qdrant, Redis):
```bash
make infra
```

Run migrations:
```bash
make migrate
```

Start backend, Celery worker, and frontend in separate terminals:
```bash
make api
make celery
make frontend
```

## Production

```bash
docker compose -f docker-compose.prod.yml up -d
```

Pull the LLM model on first run:
```bash
docker exec codementor_ollama ollama pull qwen2.5-coder:7b
```

## Makefile Reference

| Command | Description |
|---------|-------------|
| `make infra` | Start dev infrastructure |
| `make api` | Start FastAPI server |
| `make celery` | Start Celery worker |
| `make frontend` | Start React dev server |
| `make migrate` | Run Alembic migrations |
| `make migration msg="..."` | Create new migration |
| `make lint` | Run ruff linter |
| `make test` | Run tests |