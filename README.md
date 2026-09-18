# StreetLens — Pavement Condition Dashboard

Flask + Jinja2 app with real login/register backed by a Postgres database
(Neon), deployable to Vercel.

## What changed for Vercel + Neon

- `app.py` now uses **Flask-SQLAlchemy** for a real `users` table (register,
  login, logout, password hashing) instead of the earlier stub routes.
- `config.py` reads `DATABASE_URL` / `SECRET_KEY` from the environment.
- `static/` moved to `public/static/` — Vercel serves that from its CDN
  directly, per Vercel's Flask deployment guide. `url_for('static', ...)`
  still generates the same `/static/...` URLs, so no template changes were
  needed.
- `vercel.json` bumps the function timeout a bit (Neon's first connection
  after idling can be slow on a cold start).
- Tables are created automatically on startup (`db.create_all()`), so you
  don't need a separate migration step for this simple schema.

## 1. Create the Neon database

1. Sign in at [neon.tech](https://neon.tech) and create a project (any
   region close to your Vercel deployment).
2. Open the project's **Connection Details** and copy the connection string
   with **pooled connection** enabled (host containing `-pooler`) — this is
   the one that works reliably from serverless functions. It looks like:
   ```
   postgresql://<user>:<password>@<host>-pooler.<region>.aws.neon.tech/<db>?sslmode=require
   ```

## 2. Configure environment variables

Copy `.env.example` to `.env` for local development:

```bash
cp .env.example .env
```

Fill in:
- `DATABASE_URL` — the Neon pooled connection string from step 1
- `SECRET_KEY` — any random string, e.g.
  `python -c "import secrets; print(secrets.token_hex(32))"`

## 3. Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
```

Visit `http://127.0.0.1:5000`, register an account, then sign in — the user
row lands in your Neon `users` table.

## 4. Deploy to Vercel

Vercel auto-detects Flask from `app.py` (no build config needed). Using the
CLI:

```bash
npm i -g vercel
vercel login
vercel            # first deploy — links/creates the project
```

Then add the same two environment variables in the Vercel dashboard
(**Project → Settings → Environment Variables**, or via CLI):

```bash
vercel env add DATABASE_URL
vercel env add SECRET_KEY
```

Redeploy so the function picks up the new env vars:

```bash
vercel --prod
```

Or connect the GitHub repo in the Vercel dashboard and it will build on every
push once the env vars above are set under Project Settings.

## Notes

- `SECRET_KEY` must be set in Vercel — Flask sessions (and therefore login)
  won't work without it.
- If you outgrow `db.create_all()` (e.g. need real migrations across schema
  changes), switch to Flask-Migrate/Alembic and run `flask db upgrade`
  against `DATABASE_URL` from your machine before deploying.
- The dashboard's distress/pill data is still static demo data in `app.py`
  (`DISTRESS`, `PILLS`) — wire those to their own DB tables the same way
  `User` is wired, when you're ready to persist inspection results.
