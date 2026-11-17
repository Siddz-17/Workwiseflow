# Deploying WorkflowWise

Three free accounts, about 20 minutes. Do the steps in order, because each one needs a value from the one before.

| Piece | Host | Free tier notes |
|---|---|---|
| Database, auth, file storage | **Supabase** | Free project; pauses after a week of inactivity |
| API (FastAPI) | **Render** | Free web service; sleeps after 15 min idle, so the first request takes ~50 s |
| Frontend (Next.js) | **Vercel** | Hobby plan |

Keep a scratch note open for the values marked **→ save**. The service role key and database password are
secrets: paste them only into the Render dashboard, never into the frontend or a chat.

---

## 1. Supabase

1. Go to https://supabase.com/dashboard → **New project**. Pick a region near you and set a database password
   (**→ save** it).
2. **SQL Editor → New query**: paste the whole of [`supabase/migrations/0001_init.sql`](supabase/migrations/0001_init.sql)
   and **Run**. It creates the tables, pgvector indexes, row-level security policies and the private `documents`
   storage bucket. Expect "Success. No rows returned".
3. **Project Settings → API** (or **Data API** / **API Keys**):
   - Project URL, like `https://abcd1234.supabase.co` → save as **SUPABASE_URL**
   - `anon` / publishable key → save as **SUPABASE_ANON_KEY** (public, used by the browser)
   - `service_role` / secret key → save as **SUPABASE_SERVICE_ROLE_KEY** (secret, used by the API only)
4. Click **Connect** (top bar) → **Transaction pooler**. Copy the URI, which looks like
   `postgresql://postgres.abcd1234:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:6543/postgres`.
   Replace `[YOUR-PASSWORD]` with your database password → save as **DATABASE_URL**.
   Use the pooler, not the direct connection: the direct host is IPv6-only and Render can't reach it.
5. **Authentication → Sign In / Providers → Email**: leave it enabled. While testing you can turn off
   **Confirm email** so new accounts can sign in immediately.

## 2. Render (API)

1. Sign in at https://dashboard.render.com with GitHub and give Render access to the `Workwiseflow` repo.
2. **New → Blueprint** → select the repo. Choose branch `main` once the PR is merged, or
   `feat/workflowwise-platform` to deploy before merging. Render reads `render.yaml` and proposes one free
   web service, `workflowwise-api`.
3. Fill in the secret values it asks for:
   - `DATABASE_URL`: from step 1.4
   - `SUPABASE_URL`: from step 1.3
   - `SUPABASE_SERVICE_ROLE_KEY`: from step 1.3
   - `CORS_ORIGINS`: put `http://localhost:3000` for now. You'll replace it after step 3.
   - `CORS_ORIGIN_REGEX`: leave empty for now.
4. **Apply**. The first build takes a few minutes. Then open
   `https://workflowwise-api-XXXX.onrender.com/api/health` (your service URL → save as **API_URL**). You should see
   `{"ok":true,"auth":"supabase","llm":"local",...}`.

## 3. Vercel (frontend)

1. https://vercel.com/new → import the `Workwiseflow` repo.
2. **Root Directory**: `frontend`. The framework is detected as Next.js; keep the default build settings.
3. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = API_URL (no trailing slash)
   - `NEXT_PUBLIC_SUPABASE_URL` = SUPABASE_URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = SUPABASE_ANON_KEY
4. **Deploy**. Note the production URL, like `https://workflowwise.vercel.app` → save as **WEB_URL**.

## 4. Connect them

1. **Render → workflowwise-api → Environment**:
   - set `CORS_ORIGINS` = WEB_URL (add `,http://localhost:3000` if you also develop locally)
   - optionally set `CORS_ORIGIN_REGEX` = `^https://workwiseflow-.*\.vercel\.app$` to allow Vercel preview
     deployments (adjust the prefix to your Vercel project name)
   - **Save, rebuild and deploy**
2. **Supabase → Authentication → URL Configuration**:
   - Site URL = WEB_URL
   - Redirect URLs: add `WEB_URL/app`

## 5. Try it

Open WEB_URL → **Sign in** → **Create account** → create a workspace → upload a document → ask about it.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Can't reach the API" on /app | The Render service is asleep (wait ~1 min and reload), or `NEXT_PUBLIC_API_URL` is wrong. After changing a `NEXT_PUBLIC_*` value, redeploy on Vercel. |
| Browser console shows a CORS error | `CORS_ORIGINS` on Render must match WEB_URL exactly (https, no trailing slash). |
| `401 Invalid token` | Older Supabase projects sign tokens with a shared secret. Copy **JWT Secret** (Settings → API / JWT Keys → Legacy) into Render as `SUPABASE_JWT_SECRET`. |
| Upload stays "failed" with a storage error | Step 1.2 didn't run fully (no `documents` bucket), or the service role key is wrong. |
| Render build fails on PyMuPDF | Make sure `PYTHON_VERSION` is `3.12.10` (set by the blueprint). |

## Turning on Gemini later

Add `GEMINI_API_KEY` in Render → Environment and redeploy. Search vectors change when the embedding provider
changes, so reprocess existing documents and meetings afterwards (the ↻ button on each).

## Optional: background worker

Uploads are processed inside the API process, which is fine at small scale. For a dedicated queue (paid Render
plan): create a Render **Key Value** instance, add its URL as `REDIS_URL` on the API, and add a **Background
Worker** with root `backend`, build `pip install -r requirements.txt`, start `python worker.py`, and the same
environment variables as the API.
