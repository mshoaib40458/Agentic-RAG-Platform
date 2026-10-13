# Agentic RAG Platform

Document-grounded question answering with hybrid retrieval, reranking, and an
LLM verification workflow — plus a web client to upload sources, ask questions,
and inspect answers with citations.

**Stack:** FastAPI · LlamaIndex · LangGraph · Groq · Qdrant · SQLAlchemy 2.0 ·
React 19 · TypeScript · Vite · Tailwind CSS

---

## Overview

The platform ingests documents into a vector store, retrieves the most relevant
passages for a question (dense + BM25 fused with reciprocal rank fusion), reranks
them, generates an answer with an LLM, and then **verifies** that answer against
the retrieved evidence. When verification fails it can retry or abstain, so
answers never silently drift from the sources.

```
plan -> retrieve (loop over sub-queries) -> grade -+-> generate -> verify -+-> respond
                                                   |                        +-> generate (retry)
                                                   +-> abstain ------------> respond
```

---

## Repository layout

```
backend/    FastAPI service, retrieval + agent workflow, evaluation harness
frontend/   React + Vite web client
```

Each package has its own README with full setup, configuration, and scripts:

- **Backend** → [`backend/README.md`](backend/README.md)
- **Frontend** → [`frontend/README.md`](frontend/README.md)

---

## Quickstart

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell

python -m pip install -e ".[dev]"

copy .env.example .env            # then set GROQ_API_KEY
alembic upgrade head              # create/migrate the database schema
python -m uvicorn app.main:app --reload
```

> Run every command inside the activated venv (prompt shows `(.venv)`) and start
> the server with `python -m uvicorn` — not a bare `uvicorn` — so the venv's
> packages are used.

API + OpenAPI docs: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Web app: http://localhost:5173

> The frontend dev server proxies `/api` to `http://127.0.0.1:8000`, so run the
> backend first.

---

## Features

- **Grounded answers** — every response carries citations back to document
  passages, with a verification status (`supported`, `partially_supported`,
  `unsupported`, `skipped`).
- **Hybrid retrieval** — dense embeddings combined with BM25 via RRF, followed
  by an optional cross-encoder reranker.
- **Agent workflow** — a LangGraph state machine that plans sub-queries,
  retrieves, grades, generates, verifies, and can retry or abstain.
- **Documents** — upload PDF/TXT/DOCX, track ingestion status, and organise by
  category and collection.
- **Evaluations** — score retrieval quality (Recall@k, Precision@k, MRR, nDCG@k,
  hit-rate) and answer quality (token-F1) against labelled datasets, with
  pass/fail thresholds.
- **Observability** — query analytics (latency p50/p95, abstention rate,
  verification/intent breakdowns) via `/api/v1/query/analytics`.
- **Feedback** — thumbs up/down on answers for later review.
- **Auth & RBAC** — JWT access/refresh with role-based permissions.

---

## Access model

| Role | Permissions |
|---|---|
| `admin` | Full access |
| `document_manager` | Upload / manage / delete documents |
| `user` | Read accessible documents and query |
| `evaluator` | Read + query + run evaluations |

The first registered account becomes an administrator (bootstrap); later
self-registrations are forced to `user`.
