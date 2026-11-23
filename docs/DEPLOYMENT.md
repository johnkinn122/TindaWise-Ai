# Deploying the public demo (free)

Status: 📋 prepared, not deployed yet. The code and config are ready; the accounts below don't
exist yet.

| Piece | Host (free plan) | Notes |
|---|---|---|
| Web app (`apps/web`) | Vercel Hobby | Free for personal, non-commercial use. A portfolio demo qualifies |
| API (`services/api`) | Render free web service | **Sleeps after 15 minutes without requests; the next one waits 30-60 s while it wakes** |
| Database | Neon free | PostgreSQL with 1 GB storage per project. Plenty for the demo |

Cost: $0. None of the three should ask for a card on the free plans. Check each sign-up page,
since free plans change.

## How the demo is set up

- **`DEMO_MODE=true`** on both the API and the web app:
  - Sign-up is off (the API refuses it, and the sign-in page lists the demo accounts instead).
  - Every screen shows a "Public demo: sample data that may be reset" banner.
  - The seed and reset scripts are allowed to run against the production database. Without
    demo mode they refuse, so these public-password accounts never reach a real store.
- **Anyone can change the demo data**, because visitors share the demo accounts.
  `scripts.reset_demo` puts it back (see "Resetting the demo").
- **Migrations run on every API start** (`alembic upgrade head`). Render's pre-deploy step is
  for paid plans only, and an up-to-date schema makes this a no-op.
- The web app talks to the API from its server (Vercel functions), never from the browser, so
  the API address and session tokens stay server-side.

## 1. Database: Neon

1. Sign up at neon.com with GitHub.
2. Create a project named `tindawise`, region **AWS Asia Pacific (Singapore)**, Postgres 17.
3. On the project dashboard, click **Connect**, turn **Connection pooling off** and copy the
   connection string. It looks like
   `postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
   - Use the direct connection, not the pooled one. The API keeps its own small pool, and
     psycopg's prepared statements can fail behind Neon's transaction-mode pooler.
   - Keep the string private. It contains the database password.

## 2. Load the demo data (from your computer)

In **a new PowerShell window**, from `services/api`:

```powershell
$env:DATABASE_URL = "<the Neon connection string>"
$env:ENVIRONMENT = "production"
$env:DEMO_MODE = "true"

.venv/Scripts/alembic upgrade head        # create the tables
.venv/Scripts/python -m scripts.seed      # Aling Nena's Mini-Mart (sample) + 3 demo accounts
```

Optional: the second store, with two years of synthetic sales, which fills the charts,
reorder suggestions and reports:

```powershell
# From services/ml (its own virtual environment): history ending yesterday.
.venv/Scripts/python -m tindawise_ml generate --end <yesterday, e.g. 2026-11-22> --out ../api/sample_history.csv
# Back in services/api, same window:
.venv/Scripts/python -m scripts.seed_sample_history --csv sample_history.csv
```

**Close this PowerShell window when you're done.** The variables last only for this window.
Closing it means later local commands use your local database again, not the demo's.

## 3. API: Render

1. Sign up at render.com with GitHub, and allow it to read this repository.
2. **New → Blueprint**, pick the repository. Render reads `render.yaml` at the repo root and
   proposes one free web service, `tindawise-api`, in Singapore.
3. It asks for two values:
   - `DATABASE_URL`: the Neon connection string from step 1, pasted as is (the API converts
     `postgresql://` itself).
   - `CORS_ORIGINS`: enter `https://example.com` for now and fix it in step 5.
4. Create it and wait for the first deploy. The log should show the build, `alembic upgrade
   head`, then Uvicorn starting.
   - Check the Python version in the build log (`render.yaml` sets `PYTHON_VERSION` to 3.13).
     If Render used another version, set it in the service's settings.
5. Open `https://<your-service>.onrender.com/health`. Expect
   `{"status":"ok","database":"ok"}`.

## 4. Web app: Vercel

1. Sign up at vercel.com with GitHub (the free Hobby plan).
2. **Add New → Project**, import the repository.
3. Set **Root Directory** to `apps/web`. Vercel detects Next.js and the npm workspace.
4. Add environment variables (Production) **before** the first deploy. Some pages are built
   ahead of time, so a change only applies after a redeploy:
   - `API_URL`: `https://<your-service>.onrender.com` (no trailing slash needed)
   - `DEMO_MODE`: `true`
5. Deploy. Note the site's address, e.g. `https://tindawise.vercel.app`.

## 5. Finish and check

1. On Render, set `CORS_ORIGINS` to the Vercel address and save. Render redeploys.
2. Open the Vercel site. The sign-in page lists the demo accounts.
   - The first sign-in after a quiet spell can take up to a minute while the API wakes. The
     page starts waking it as soon as it opens.
3. Sign in as `owner@example.com`, check the demo banner, the Overview, Products and Sell.
4. Open `/signup`. It should say sign-up is off.

## Updating

Pushing to `main` (a merged pull request) redeploys both: Vercel builds the web app, and
Render rebuilds the API, which runs any new migration as it starts.

## Resetting the demo

As in step 2, in a new PowerShell window with the three variables set, from `services/api`:

```powershell
.venv/Scripts/python -m scripts.reset_demo --yes-delete-everything
```

This empties every table (including the activity log) and seeds the demo store again. Run
`seed_sample_history` again if you want the second store back. Close the window afterwards.

## Known limits

- **Cold starts.** The free API sleeps after 15 idle minutes. A free uptime pinger hitting
  `/health` every 10 minutes would keep it awake (one service uses about 720 of Render's 750
  free hours a month), but the demo works without one.
- **Synthetic sample data** only. The sample history store's sales stop on the day before it
  was seeded, so over time its "last 7 days" look quiet.
- **Vercel Hobby is non-commercial.** A real store using this would need paid plans.
- The demo accounts' password is public (it's in `scripts/seed.py`). Demo mode is what makes
  that acceptable. Never set `DEMO_MODE` on a server with real data.
