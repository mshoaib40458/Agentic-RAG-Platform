# Agentic RAG Platform — Frontend

Web client for the Agentic RAG Platform: ask questions over your documents, see
grounded answers with citations, and manage sources, history, evaluations, and
users.

**Stack:** React 19 · TypeScript · Vite · Tailwind CSS · shadcn/ui ·
TanStack Query · React Router · Axios

---

## Features

- **Ask** — question box with optional filters (category, collection, top-k),
  streamed-style loading state, verified answers, and citation cards.
- **Documents** — upload (PDF/TXT/DOCX), search, filter, edit metadata, delete,
  and at-a-glance stats.
- **History** — paginated list of past questions with expandable answers and
  sources.
- **Evaluations** — start runs against a dataset and inspect quality metrics.
- **Users** — admin-only role and active-status management.
- **Auth** — login/register, JWT access + refresh with transparent token refresh.
- **Theming** — light / dark / system theme, fully responsive, RBAC-aware nav.

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

Open http://localhost:5173

The dev server proxies `/api` to `http://127.0.0.1:8000`, so no CORS setup is
needed locally.

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
| `npm run build` | Type-check and build for production (`dist/`) |
| `npm run preview` | Preview the production build |
| `npm run typecheck` | Run `tsc` with no emit |
| `npm run lint` | Run ESLint |

---

## Project structure

```
src/
  api/           typed endpoint wrappers (auth, documents, query, …)
  components/    shared UI + shadcn/ui primitives (ui/), layout shell
  contexts/      auth and theme providers
  lib/           api client, token store, permissions, formatters, query keys
  pages/         route-level pages (lazy-loaded)
  types/         shared API types
  App.tsx        routes, guards, and providers
  main.tsx       app entry
```

---

## Auth model

Tokens are stored in `localStorage` (`arp.access_token`, `arp.refresh_token`).
The Axios client attaches the access token to every request and, on a `401`,
performs a single refresh-and-retry before clearing the session. The UI mirrors
the backend RBAC roles (`admin`, `document_manager`, `evaluator`, `user`) to
show or hide navigation and actions.

---

## Notes

- Pages are code-split via `React.lazy`, so each route loads on demand.
- The backend's "first registered user is admin" rule means the very first
  account you register through `/register` becomes the administrator.
