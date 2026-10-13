<div align="center">

# Agentic RAG Platform

**Document-grounded question answering with hybrid retrieval, reranking, and a verifiable agentic workflow.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6)](https://www.typescriptlang.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agentic-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector%20store-DC244C)](https://qdrant.tech/)

</div>

---

## Overview

The Agentic RAG Platform ingests documents into a vector store, retrieves the
passages most relevant to a question, and produces an answer that is **verified
against the retrieved evidence** before it is returned. A LangGraph state machine
plans sub-queries, grades evidence, generates an answer, verifies it, and — when
verification fails — retries or abstains, so answers never silently drift from
the sources. Every answer carries citations back to its source passages.

Repository layout:

```
backend/    FastAPI service — retrieval, agent workflow, evaluation harness
frontend/   React + Vite single-page web client
```

## Features

- **Grounded answers** — citations with a verification status (`supported`,
  `partially_supported`, `unsupported`, `skipped`).
- **Agentic workflow** — plan → retrieve → grade → generate → verify, with
  retry/abstain paths and hard iteration/timeout caps.
- **Hybrid retrieval** — dense embeddings fused with BM25 via reciprocal rank
  fusion, followed by an optional cross-encoder reranker.
- **Conversations** — persist multi-turn chat threads; list, replay, and delete.
- **Document management** — upload PDF/TXT/DOCX, track ingestion, edit metadata,
  delete, and view ingestion stats.
- **Evaluations** — score retrieval (Recall@k, Precision@k, MRR, nDCG@k,
  hit-rate) and answers (token-F1) against labelled datasets, with pass/fail
  thresholds.
- **Observability** — query analytics: latency p50/p95, abstention rate, and
  verification/intent breakdowns.
- **Auth & RBAC** — JWT access/refresh with Argon2id password hashing, role-based
  permissions, and an optional `DISABLE_AUTH` demo mode that skips login.

## Architecture

```
plan -+- no_retrieval ------------------------------------------> respond
      +- respond
      +- retrieve (loop over sub-queries) -> grade -+-> generate -> verify -+-> respond
                                                    |                        +-> generate (retry)
                                                    +-> abstain ------------> respond
```

```
HTTP (FastAPI)
  api/v1/          routers: auth, users, documents, query, conversations, feedback, evaluations, health
  api/deps.py      auth / RBAC / pagination dependencies
  services/        business logic (auth, documents, query, conversations, feedback, evaluation)
  repositories/    data access (SQLAlchemy 2.0 async)
  agent/           LangGraph state graph, nodes, runner
  retrieval/       dense + BM25 + RRF fusion + hybrid orchestration
  ingestion/       extractors (PDF/TXT/DOCX), chunking, ingestion pipeline
  llm/             Groq chat model, embeddings, reranker
  evaluation/      evaluation harness and metrics
  db/              engine/session + ORM models
  core/            config, logging, security, exceptions, constants
```

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| Agent | LangGraph, LangChain Core |
| LLM | Groq (`openai/gpt-oss-20b` by default) |
| Embeddings / reranking | Sentence-Transformers; optional `bge-reranker-base` |
| Vector store | Qdrant (embedded `qdrant_local` or server) |
| Database | SQLAlchemy 2.0 async (SQLite default, Postgres optional) |
| Web client | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, React Router |

## Getting started

**Prerequisites:** Python 3.11+, Node.js 18+ (developed on 22), and a
[Groq API key](https://console.groq.com/) for answer generation.

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Windows PowerShell
# source .venv/bin/activate            # macOS / Linux

python -m pip install -e ".[dev]"
copy .env.example .env                 # then set GROQ_API_KEY
alembic upgrade head
python -m uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

- API + Swagger UI: <http://127.0.0.1:8000> and <http://127.0.0.1:8000/docs>
- Web app: <http://localhost:5173> (Vite proxies `/api` to the backend, so start
  the backend first)

Register the first account at `/register` — it becomes the workspace
administrator.

> To skip login for a local demo, set `DISABLE_AUTH=true` in `backend/.env` and
> restart the backend. Every request then runs as an administrator and the web
> client opens straight to the dashboard.

## Configuration

Settings are read from `backend/.env` (template: `backend/.env.example`).

| Setting | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | Swap to `postgresql+asyncpg://...` (install `.[postgres]`) |
| `VECTOR_STORE` | `qdrant_local` | Embedded Qdrant; use `qdrant` for a server |
| `EMBEDDING_PROVIDER` | `local` | `local` (Sentence-Transformers) or `huggingface` |
| `RERANKER_ENABLED` | `false` | Enables the cross-encoder (extra model download) |
| `DISABLE_AUTH` | `false` | `true` skips login and runs every request as an administrator |
| `GROQ_API_KEY` | — | Required for answer generation |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Any currently supported Groq model |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed web origins |

## API reference

Base path: `/api/v1`. All endpoints except the public auth/health routes require
a `Bearer` access token.

| Method | Path | Description | Access |
|---|---|---|---|
| `GET` | `/health` | Service health | Public |
| `POST` | `/auth/register` | Create an account | Public |
| `POST` | `/auth/login` | Obtain access + refresh tokens | Public |
| `POST` | `/auth/refresh` | Exchange a refresh token | Public |
| `GET` | `/auth/config` | Public auth settings (e.g. login disabled) | Public |
| `GET` | `/auth/me` | Current user profile | Authenticated |
| `GET` | `/users` | List users | `users:manage` |
| `PATCH` | `/users/{id}` | Update role / active status | `users:manage` |
| `GET` | `/documents` | List documents (paged, searchable) | `documents:read` |
| `GET` | `/documents/stats` | Ingestion statistics | `documents:read` |
| `POST` | `/documents` | Upload a document | `documents:write` |
| `GET` | `/documents/{id}` | Document detail | `documents:read` |
| `PATCH` | `/documents/{id}` | Update metadata | `documents:write` |
| `DELETE` | `/documents/{id}` | Delete a document and its passages | `documents:delete` |
| `POST` | `/query` | Ask a question (optional `conversation_id`) | `query:execute` |
| `GET` | `/query` | Query history (paged) | `query:execute` |
| `GET` | `/query/analytics` | Latency / abstention / verification analytics | `query:execute` |
| `GET` | `/query/{id}` | Query detail with answer + citations | `query:execute` |
| `GET` | `/query/{id}/status` | Query processing status | `query:execute` |
| `GET` | `/conversations` | List conversations (paged) | `query:execute` |
| `POST` | `/conversations` | Create a conversation | `query:execute` |
| `GET` | `/conversations/{id}` | Conversation detail with its turns | `query:execute` |
| `DELETE` | `/conversations/{id}` | Delete a conversation | `query:execute` |
| `POST` | `/feedback` | Submit answer feedback | Authenticated |
| `GET` | `/feedback/query/{query_id}` | Feedback for a query | Authenticated |
| `POST` | `/evaluations` | Start an evaluation run | `evaluations:run` |
| `GET` | `/evaluations` | List evaluation runs (paged) | `evaluations:run` |
| `GET` | `/evaluations/{run_id}` | Evaluation detail + metrics | `evaluations:run` |

## Access model

| Role | Permissions |
|---|---|
| `admin` | Full access |
| `document_manager` | Read / upload / manage / delete documents, query |
| `user` | Read accessible documents, query |
| `evaluator` | Read documents, query, run evaluations |

A user can read documents they **own** or that live in the reserved `public`
collection; admins read everything. The first registered account becomes an
administrator; later self-registrations are forced to `user`.

## Testing

**Backend** (`cd backend`)

```bash
pytest                 # unit + integration
ruff check app tests   # lint
mypy app               # static types
```

**Frontend** (`cd frontend`)

```bash
npm test               # Vitest + React Testing Library
npm run typecheck      # tsc
npm run lint           # ESLint
npm run build          # production build
```

Integration tests run against an isolated database and vector store with a stub
embedding model, so no large models are downloaded.

## License

Proprietary. All rights reserved.
