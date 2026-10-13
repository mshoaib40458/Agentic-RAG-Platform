<div align="center">

# Agentic RAG Platform

**Document-grounded question answering with hybrid retrieval, reranking, and an LLM verification workflow.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6)](https://www.typescriptlang.org/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.12%2B-7C3AED)](https://www.llamaindex.ai/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agentic-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector%20store-DC244C)](https://qdrant.tech/)
[![License](https://img.shields.io/badge/License-Proprietary-lightgrey)](#license)

</div>

---

## Overview

The Agentic RAG Platform ingests your documents into a vector store, retrieves
the passages most relevant to a question, and produces an answer that is
**verified against the retrieved evidence** before it is returned. Instead of a
single "retrieve → generate" pass, a LangGraph state machine plans sub-queries,
grades evidence, generates an answer, verifies it, and — when verification
fails — retries or abstains. Every answer carries citations back to the source
passages, so responses never silently drift from the documents.

The repository is a two-package monorepo:

```
backend/    FastAPI service — retrieval, agent workflow, evaluation harness
frontend/   React + Vite single-page web client
```

---

## Key features

- **Grounded answers** — each response includes citations with a verification
  status (`supported`, `partially_supported`, `unsupported`, `skipped`).
- **Hybrid retrieval** — dense embeddings fused with BM25 via Reciprocal Rank
  Fusion (RRF), followed by an optional cross-encoder reranker.
- **Agentic workflow** — a LangGraph state machine that plans, retrieves,
  grades, generates, verifies, retries, or abstains, with hard iteration and
  timeout caps.
- **Document management** — upload PDF / TXT / DOCX, track ingestion status, and
  organise sources by category and collection.
- **LlamaIndex-powered ingestion** — page-aware chunking via LlamaIndex Core
  `SentenceSplitter`, with a built-in fallback splitter if the library is
  unavailable.
- **Evaluations** — score retrieval quality (Recall@k, Precision@k, MRR, nDCG@k,
  hit-rate) and answer quality (token-F1) against labelled datasets, with
  pass/fail thresholds.
- **Observability** — query analytics (latency p50/p95, abstention rate,
  verification and intent breakdowns).
- **Feedback** — thumbs up/down on answers for later review.
- **Auth & RBAC** — JWT access/refresh with role-based permissions.

---

## Architecture

The agent runs as a directed graph. The `plan` node decides whether retrieval is
needed at all, and the `verify` node decides whether to accept, retry, or
abstain:

```
plan -+- no_retrieval ------------------------------------------> respond
      +- respond
      +- retrieve (loop over sub-queries) -> grade -+-> generate -> verify -+-> respond
                                                    |                        +-> generate (retry)
                                                    +-> abstain ------------> respond
```

The backend is layered so HTTP, business logic, and data access stay separate:

```
HTTP (FastAPI)
  api/v1/          routers: auth, users, documents, query, feedback, evaluations, health
  api/deps.py      auth / RBAC / pagination dependencies
  services/        business logic (auth, documents, query, feedback, evaluation)
  repositories/    data access (SQLAlchemy 2.0 async)
  agent/           LangGraph state graph, nodes, runner
  retrieval/       dense + BM25 + RRF fusion + hybrid orchestration
  ingestion/       extractors (PDF/TXT/DOCX), LlamaIndex chunking, ingestion pipeline
  llm/             Groq chat model, embeddings, reranker (provider-agnostic)
  evaluation/      evaluation harness (Recall@k, Precision@k, MRR, nDCG@k, hit-rate, answer F1)
  db/              engine/session + ORM models
  core/            config, logging, security, exceptions, constants
```

---

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Agent orchestration | LangGraph, LangChain Core |
| LLM | Groq (default `openai/gpt-oss-20b`) |
| Embeddings | Sentence-Transformers (`BAAI/bge-small-en-v1.5`) |
| Reranking | Cross-encoder (`BAAI/bge-reranker-base`, optional) |
| Chunking | LlamaIndex Core `SentenceSplitter` (with a fallback splitter) |
| Vector store | Qdrant (embedded `qdrant_local` or server) |
| Persistence | SQLAlchemy 2.0 async, SQLite / PostgreSQL, Alembic |
| Security | PyJWT, Argon2 |
| Frontend | React 19, TypeScript (strict), Vite, Tailwind CSS, shadcn/ui |
| Client data | TanStack Query v5, React Router v7, Axios, Zod |
| Testing | pytest (backend), Vitest + React Testing Library (frontend) |

---

## Repository layout

```
agentic-rag-platform/
├── backend/
│   ├── app/                 FastAPI application (see Architecture)
│   ├── alembic/             Database migrations
│   ├── data/                Runtime DB, uploads, vectors, eval datasets
│   ├── scripts/             build_eval_dataset.py, sweep_eval.py
│   ├── tests/               unit/ + integration/
│   ├── pyproject.toml
│   └── README.md            Backend setup, configuration, API notes
├── frontend/
│   ├── src/                 api/ components/ contexts/ lib/ pages/ types/
│   ├── package.json
│   └── README.md            Frontend setup, scripts, structure
├── data/                    Local runtime artifacts (git-ignored)
└── README.md                This file
```

Each package has its own README with the full details:
[**backend**](backend/README.md) · [**frontend**](frontend/README.md).

---

## Getting started

**Prerequisites**

- Python **3.11+**
- Node.js **18+** (developed on 22)
- A [Groq API key](https://console.groq.com/) for answer generation

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Windows PowerShell
# source .venv/bin/activate            # macOS / Linux

python -m pip install -e ".[dev]"

copy .env.example .env                 # then set GROQ_API_KEY
alembic upgrade head                   # create / migrate the database schema
python -m uvicorn app.main:app --reload
```

> Run every command inside the activated venv (the prompt shows `(.venv)`) and
> start the server with `python -m uvicorn` — not a bare `uvicorn` — so the
> venv's packages are used. If activation is blocked, allow it for the current
> shell with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

- API: <http://127.0.0.1:8000>
- OpenAPI docs (Swagger UI): <http://127.0.0.1:8000/docs>

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

- Web app: <http://localhost:5173>

> The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so start the
> backend first.

### 3. Smoke test

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Register the first account at <http://localhost:5173/register> — it becomes the
workspace administrator.

---

## Configuration

Backend settings are read from `backend/.env` (template:
[`backend/.env.example`](backend/.env.example)). The essentials:

| Setting | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | Swap to `postgresql+asyncpg://...` (install `.[postgres]`) |
| `VECTOR_STORE` | `qdrant_local` | Embedded Qdrant; use `qdrant` for a server |
| `EMBEDDING_PROVIDER` | `local` | `local` (Sentence-Transformers) or `huggingface` |
| `RERANKER_ENABLED` | `false` | Enables the cross-encoder for a precision lift (extra model download) |
| `GROQ_API_KEY` | — | Required for answer generation |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Any currently supported Groq model |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed web origins |

Frontend settings live in `frontend/.env` (template:
[`frontend/.env.example`](frontend/.env.example)):

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_URL` | `/api/v1` | Keep the `/api/v1` suffix; the dev proxy forwards it |

---

## API reference

Base path: `/api/v1`. All endpoints except the public auth/health routes require
a `Bearer` access token.

| Method | Path | Description | Access |
|---|---|---|---|
| `GET` | `/health` | Service health | Public |
| `POST` | `/auth/register` | Create an account | Public |
| `POST` | `/auth/login` | Obtain access + refresh tokens | Public |
| `POST` | `/auth/refresh` | Exchange a refresh token for a new access token | Public |
| `GET` | `/auth/me` | Current user profile | Authenticated |
| `GET` | `/users` | List users | `users:manage` |
| `PATCH` | `/users/{user_id}` | Update role / active status | `users:manage` |
| `GET` | `/documents/stats` | Ingestion statistics | `documents:read` |
| `GET` | `/documents` | List documents (paged, searchable) | `documents:read` |
| `POST` | `/documents` | Upload a document | `documents:write` |
| `GET` | `/documents/{id}` | Document detail | `documents:read` |
| `PATCH` | `/documents/{id}` | Update metadata | `documents:write` |
| `DELETE` | `/documents/{id}` | Delete a document and its passages | `documents:delete` |
| `POST` | `/query` | Ask a question | `query:execute` |
| `GET` | `/query` | Query history (paged) | `query:execute` |
| `GET` | `/query/analytics` | Latency / abstention / verification analytics | `query:execute` (scoped) |
| `GET` | `/query/{id}` | Query detail with answer + citations | `query:execute` |
| `GET` | `/query/{id}/status` | Query processing status | `query:execute` |
| `POST` | `/feedback` | Submit answer feedback | Authenticated |
| `GET` | `/feedback/query/{query_id}` | Feedback for a query | Authenticated |
| `POST` | `/evaluations` | Start an evaluation run | `evaluations:run` |
| `GET` | `/evaluations` | List evaluation runs (paged) | `evaluations:run` |
| `GET` | `/evaluations/{run_id}` | Evaluation detail + metrics | `evaluations:run` |

---

## Access model

Permissions are enforced by role on the API and mirrored in the UI.

| Role | Permissions |
|---|---|
| `admin` | Full access |
| `document_manager` | Upload / manage / delete documents |
| `user` | Read accessible documents and query |
| `evaluator` | Read + query + run evaluations |

A user can read documents they **own** or that live in the reserved `public`
collection; admins read everything. The **first registered account becomes an
administrator** (bootstrap); later self-registrations are forced to `user`.

---

## Evaluation

Datasets are JSON Lines (see
[`backend/data/eval/README.md`](backend/data/eval/README.md)). Build a starter
set from past successful queries and sweep retrieval modes offline:

```bash
cd backend
python scripts/build_eval_dataset.py --output data/eval/dataset.jsonl
python scripts/sweep_eval.py --dataset data/eval/dataset.jsonl
```

Metrics per run: `recall_at_k`, `precision_at_k`, `mrr`, `ndcg_at_k`,
`hit_rate_at_k`, and — with answer metrics enabled — `answer_f1`. A run can
declare pass/fail thresholds through its config; results expose
`metrics.passed` and `metrics.threshold_failures`.

---

## Testing and quality gates

**Backend**

```bash
cd backend
pytest                 # unit + integration tests
ruff check .           # lint
mypy app               # static types
```

**Frontend**

```bash
cd frontend
npm test               # Vitest + React Testing Library
npm run typecheck      # tsc --noEmit
npm run lint           # ESLint
npm run build          # production build
```

Integration tests run against an isolated database and vector store with a stub
embedding model, so no large models are downloaded during CI.

---

## Notes

- Heavy ML dependencies (Sentence-Transformers / PyTorch) load lazily and are
  warmed in a background task at startup, so the API is ready immediately and
  the first query is not penalised by model loading. The cross-encoder is only
  warmed when `RERANKER_ENABLED=true`.
- Alembic owns the schema. In development the app also creates tables on
  startup when no migrations are applied; production deployments should rely on
  `alembic upgrade head`.
- `SECRET_KEY` and `GROQ_API_KEY` are server-side only and are never returned by
  any endpoint.

---

## License

Proprietary. All rights reserved. See `backend/pyproject.toml` for the license
declaration.
