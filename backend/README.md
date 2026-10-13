# Agentic RAG Platform — Backend

Document-grounded question answering with hybrid retrieval, reranking, and a
LangGraph verification workflow.

**Stack:** FastAPI · LlamaIndex · LangGraph · Groq · Qdrant · SQLAlchemy 2.0

---

## Architecture

```
HTTP (FastAPI)
  api/v1/          routers: auth, users, documents, query, feedback, evaluations, health
  api/deps.py      auth / RBAC / pagination dependencies
  services/        business logic (auth, documents, query, feedback, evaluation)
  repositories/    data access (SQLAlchemy 2.0 async)
  agent/           LangGraph state graph + nodes + runner
  retrieval/       dense + BM25 + RRF fusion + hybrid orchestration
  ingestion/       extractors (PDF/TXT/DOCX), chunking, ingestion pipeline
  llm/             Groq chat model, embeddings, reranker (provider-agnostic)
  evaluation/      evaluation harness (Recall@k, Precision@k, MRR, nDCG@k, hit-rate, answer F1)
  db/              engine/session + ORM models
  core/            config, logging, security, exceptions, constants
```

Request flow for a question:

```
plan -+- no_retrieval ------------------------------------------> respond
      +- respond
      +- retrieve (loop over sub-queries) -> grade -+-> generate -> verify -+-> respond
                                                    |                        +-> generate (retry)
                                                    +-> abstain ------------> respond
```

---

## Quickstart

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell

python -m pip install -e ".[dev]"

copy .env.example .env            # then set GROQ_API_KEY
alembic upgrade head              # create/migrate the database schema
python -m uvicorn app.main:app --reload
```

> Run every command inside the activated venv — the prompt should show `(.venv)`.
> Always start the server with `python -m uvicorn` (not a bare `uvicorn`) so the
> venv's packages are used. If activation is blocked (`Activate.ps1 cannot be
> loaded`), allow it for the current shell with
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

OpenAPI docs: http://127.0.0.1:8000/docs

---

## Configuration

All settings come from environment variables. Key choices:

| Setting | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite | Swap to `postgresql+asyncpg://...` (install `.[postgres]`) |
| `VECTOR_STORE` | `qdrant_local` | Embedded Qdrant; use `qdrant` for a server |
| `EMBEDDING_PROVIDER` | `local` | `local` (Sentence-Transformers) or `huggingface` |
| `RERANKER_ENABLED` | `false` | Enable the cross-encoder for a precision lift (downloads a model) |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Any currently supported Groq model |

---

## Database migrations

Alembic owns the schema. The async database URL is rewritten to a sync driver at
migration time, so the same commands work for both SQLite and Postgres:

```bash
alembic upgrade head                                   # apply all migrations
alembic revision --autogenerate -m "describe change"   # create a new migration
alembic downgrade -1                                   # roll back one step
```

In development the app also creates tables on startup when no migrations are
applied; production deployments should rely on `alembic upgrade head`.

---

## Access model

| Role | Permissions |
|---|---|
| `admin` | Full access |
| `document_manager` | Upload / manage / delete documents |
| `user` | Read accessible documents and query |
| `evaluator` | Read + query + run evaluations |

A user can read documents they **own** or that live in the reserved `public`
collection. Admins read everything. The first registered account becomes an
administrator (bootstrap); later self-registrations are forced to `user`.

---

## Evaluation

Datasets are JSON Lines (see `data/eval/README.md`). Build a starter set from
past successful queries and sweep retrieval modes offline:

```bash
python scripts/build_eval_dataset.py --output data/eval/dataset.jsonl
python scripts/sweep_eval.py --dataset data/eval/dataset.jsonl
```

Metrics returned per run: `recall_at_k`, `precision_at_k`, `mrr`, `ndcg_at_k`,
`hit_rate_at_k`, and (with `include_answer_metrics`) `answer_f1` against
`expected_answer`. Pass gates via the run `config`, e.g.
`{"thresholds": {"recall_at_k": 0.6, "mrr": 0.7}}` — a missed gate sets
`metrics.passed=false` with `metrics.threshold_failures`.

Query observability is available at `GET /api/v1/query/analytics` (latency
p50/p95, abstention rate, verification and intent breakdowns), scoped to the
caller unless they are an admin/evaluator.

---

## Tests

```bash
pytest                 # unit + integration tests
ruff check app tests   # lint
mypy app               # static type checks
```

The integration suite uses an isolated temporary database and vector store with a
stubbed embedding model, so it runs without downloading ML weights. A heavier
end-to-end check with the real local embedding model can be run once the full
stack is installed.

---

## Notes

- Heavy ML dependencies (Sentence-Transformers / PyTorch) load lazily and are
  warmed in a background task at startup, so the API is ready immediately and
  the first query is not penalised by model loading. The cross-encoder is only
  warmed when `RERANKER_ENABLED=true`.
- `SECRET_KEY` and `GROQ_API_KEY` are server-side only and never returned by any
  endpoint.
