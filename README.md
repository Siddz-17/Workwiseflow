# WorkflowWise — your team's institutional memory

An AI workspace that remembers what your team knows, what it decided, and what needs to happen next.

Decisions happen in meetings, answers get buried in chat, requirements live in five versions of a PDF, and nobody
remembers who owned the task. WorkflowWise turns documents, meeting notes and project records into a searchable,
cited memory, and keeps track of decisions, commitments and the gaps between them.

## Features

| # | Feature | What it does |
|---|---------|--------------|
| 01 | **Ask your workspace** | RAG over documents, meeting notes and records. Every claim carries a `[n]` citation that opens the source at the exact passage. Threads persist per user. Follow-ups use the previous question as context. |
| 02 | **Meeting intelligence** | Upload a transcript (`.txt .md .vtt .srt .docx .pdf`) or paste notes. Extracts summary, attendees, decisions (with rationale and approver), action items (owner, deadline resolved from "by Friday" against the meeting date) and open questions. Owners are matched to workspace members. |
| 03 | **Decision tracker** | Keyword and semantic search; status `active / proposed / superseded / revoked`; "replaced by" chains; "still valid" re-confirmation; link back to the source meeting and quote. |
| 04 | **Action items** | Views for incomplete, overdue, no owner, mine and done. Assign owners, set due dates, advance status inline. |
| 05 | **Knowledge gaps** | *Unanswered questions*: questions Ask couldn't answer (deduplicated, counted) plus open questions from meetings. Answering one saves it to the knowledge base. *Outdated documents*: superseded versions and documents not updated or verified in `STALE_AFTER_DAYS`. *Conflicts*: similar decisions or passages that contradict each other, judged by the LLM. |
| 06 | **Team workspace** | Multiple workspaces, projects, email invites (auto-claimed on first sign-in), roles `viewer < member < admin < owner`, project-scoped search, persistent chat history. |

Re-uploading a document with the same title in the same project creates **v2** and marks v1 superseded, so answers
come from the latest version.

## Architecture

```
frontend/   Next.js 16 · TypeScript · Tailwind v4 · shadcn/ui-style components · SWR · Supabase Auth
backend/    FastAPI · SQLAlchemy 2 · pgvector · PyMuPDF · python-docx · Redis + RQ
supabase/   SQL migration (tables, HNSW indexes, RLS, storage bucket)
```

| Layer | Choice |
|---|---|
| Database | Supabase Postgres + **pgvector** (SQLite locally and in tests) |
| Auth | **Supabase Auth**: the frontend signs in, the API verifies the JWT (JWKS, or legacy HS256 secret) |
| Files | **Supabase Storage** private bucket (local disk in dev); downloads go through the API's membership check |
| Embeddings | **Gemini** `gemini-embedding-001` at 768 dims, or an offline hashing embedder |
| LLM | **Gemini Flash** behind a provider interface (`app/services/llm.py`). An offline heuristic provider implements the same tasks, so the app works with no key, and Gemini failures fall back to it. |
| Jobs | **Redis + RQ** when `REDIS_URL` is set, otherwise FastAPI background tasks |
| Deploy | **Vercel** (frontend) + **Render** (API, worker, Redis; see `render.yaml`) |
| Tests | **Pytest** (backend) + **Vitest** (frontend) |

Every API route is scoped `/api/workspaces/{ws}/…`. Every query filters on `workspace_id`, and every route checks
the caller's role. RLS policies in the migration add defense in depth for anyone querying Supabase directly.

## Run locally (no accounts needed)

Prerequisites: Python 3.11+ and Node 20+.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
python scripts/seed_demo.py demo@northwind.test   # optional demo workspace
uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Open http://localhost:3000 and sign in with any email. With `NEXT_PUBLIC_SUPABASE_URL` unset, the frontend uses dev
sign-in and the backend (`AUTH_MODE=dev`) accepts it. Use `demo@northwind.test` to see the seeded workspace.

Add `GEMINI_API_KEY` to `backend/.env` for real semantic search, answers and extraction. The offline providers are
deterministic and keyword-based, good for development but not for production. Switching embedding providers
changes the vector space, so reprocess documents afterwards.

## Production setup

1. **Supabase**: create a project, then run `supabase/migrations/0001_init.sql` in the SQL editor (or `supabase db push`).
   This creates the tables, pgvector HNSW indexes, RLS policies and the private `documents` bucket.
2. **Render**: create a Blueprint from `render.yaml`. Set `DATABASE_URL` (Supabase pooler string), `SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` and `CORS_ORIGINS` (your Vercel URL).
3. **Vercel**: import the repo with root directory `frontend`. Set `NEXT_PUBLIC_API_URL` (Render URL),
   `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. In Supabase Auth → URL configuration, add the
   Vercel domain as the site URL and redirect URL.

The migration is generated from the models, so after changing `backend/app/models.py` run
`python backend/scripts/dump_schema.py`. RLS lives in `supabase/policies.sql`.

## Tests

```powershell
cd backend; python -m pytest       # API, roles, isolation, ingestion (txt/pdf/docx), RAG, extraction, gaps
cd frontend; npm test              # citation parsing, date logic, UI primitives
cd frontend; npm run build
```

## API overview

| Area | Endpoints |
|---|---|
| Me / workspaces | `GET /api/me`, `POST/GET/PATCH/DELETE /api/workspaces[/{ws}]`, `GET /api/workspaces/{ws}/overview` |
| Team | `GET members`, `PATCH/DELETE members/{user}`, `POST/GET/DELETE invites`, `GET/POST/PATCH/DELETE projects` |
| Documents | `GET/POST documents`, `POST documents/text`, `GET documents/{id}`, `GET …/file`, `PATCH`, `POST …/reprocess`, `DELETE` |
| Ask | `POST chat/ask`, `GET chat/threads`, `GET/DELETE chat/threads/{id}` |
| Meetings | `GET/POST meetings`, `GET/DELETE meetings/{id}`, `POST …/reprocess` |
| Decisions / actions | `GET/POST/PATCH/DELETE decisions`, `GET/POST/PATCH/DELETE actions` (`?overdue&unassigned&mine&status=incomplete`) |
| Gaps | `GET gaps`, `POST gaps/scan`, `PATCH conflicts/{id}`, `PATCH questions/{id}`, `POST documents/{id}/verify` |

Interactive docs: http://localhost:8000/docs
