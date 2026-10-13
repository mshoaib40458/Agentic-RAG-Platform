# Agentic RAG Platform — Frontend

Web client for the Agentic RAG Platform: ask questions over your documents, read
grounded answers with citations, and manage conversations, sources, and
evaluations.

**Stack:** React 19 · TypeScript · Vite · Tailwind CSS · shadcn/ui ·
TanStack Query · React Router · Axios

---

## Features

- **Ask** — question box with optional filters (category, collection, top-k),
  loading state, verified answers, and citation cards.
- **Conversations** — persistent chat threads: create, switch, replay, and delete
  (delete button on each conversation row).
- **Documents** — upload (PDF/TXT/DOCX), search, filter, edit metadata, delete,
  and at-a-glance stats.
- **Evaluations** — start runs against a dataset and inspect quality metrics.
- **Auth** — login/register with JWT access + refresh and transparent token
  refresh; an optional no-login mode (`DISABLE_AUTH`) opens the app straight to
  the dashboard.
- **Theming** — light / dark / system theme, responsive, RBAC-aware navigation.

---

## Requirements

- Node.js 18+ (developed on Node 22)
- The backend running at `http://127.0.0.1:8000` (see `../backend/README.md`)

---

## Quickstart

```bash
cd frontend
npm install
copy .env.example .env        # optional; defaults work for local dev
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api` to
`http://127.0.0.1:8000`, so start the backend first and no CORS setup is needed.

---

## Configuration

Create `.env` from `.env.example`:

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_URL` | `/api/v1` | Base URL for the API. Keep the `/api/v1` suffix. |

---

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start the Vite dev server (port 5173) |
| `npm run build` | Type-check and build for production |
| `npm run typecheck` | Run `tsc` |
| `npm run lint` | Run ESLint |
| `npm test` | Run Vitest + React Testing Library |

---

## Auth

The Axios client attaches the access token to every request and, on a `401`,
performs a single refresh-and-retry before clearing the session. The UI mirrors
the backend RBAC roles (`admin`, `document_manager`, `evaluator`, `user`) to show
or hide navigation and actions. If the backend enables `DISABLE_AUTH`, the client
detects it via `GET /auth/config`, skips login, and loads the app as an
administrator.

---

## Notes

- Pages are code-split via `React.lazy`, so each route loads on demand.
- The backend's "first registered user is admin" rule means the first account
  registered through `/register` becomes the administrator.
