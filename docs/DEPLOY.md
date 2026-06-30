# Deployment Guide

## Prerequisites

- [Vercel](https://vercel.com) account (Hobby free tier is sufficient)
- [Neon](https://neon.tech) account (free tier is sufficient)
- Google Cloud project with OAuth 2.0 credentials
- Telegram bot created via [@BotFather](https://t.me/BotFather)

---

## 1. Neon DB

1. Create a new Neon project.
2. Copy the connection string from the dashboard — it looks like:
   `postgresql://user:password@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`
3. Use this as `DATABASE_URL` in Vercel env secrets (see below).

---

## 2. Google OAuth

1. Go to **Google Cloud Console → APIs & Services → Credentials**.
2. Create an **OAuth 2.0 Client ID** (Web application type).
3. Add an authorized redirect URI:
   `https://<your-project>.vercel.app/auth/callback`
4. Note the **Client ID** and **Client Secret**.

---

## 3. Vercel Environment Secrets

Set all of the following in **Vercel → Project → Settings → Environment Variables**:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `SESSION_SECRET` | Output of `openssl rand -hex 32` |
| `GOOGLE_CLIENT_ID` | From Google OAuth credentials |
| `GOOGLE_CLIENT_SECRET` | From Google OAuth credentials |
| `OAUTH_REDIRECT_URL` | `https://<your-project>.vercel.app/auth/callback` |
| `ALLOWED_EMAILS` | Comma-separated list of permitted email addresses |
| `ADMIN_EMAILS` | Comma-separated list of admin email addresses |

---

## 4. Deploy

```bash
vercel login
vercel deploy --prod
```

The cron route (`/api/cron`) is invoked by Vercel Cron — configure it in `vercel.json`:

```json
{
  "crons": [{ "path": "/api/cron", "schedule": "*/1 * * * *" }]
}
```

---

## 5. Local Development

Run tests (requires a local or test Postgres instance):

```bash
TEST_DATABASE_URL=postgresql://vnstock:vnstock@localhost:5432/vnstock_test pytest -v
```

Run the web app locally:

```bash
IGNORE_MARKET_HOURS=1 DATABASE_URL=postgresql://... uvicorn app.web.main:app --reload
```

---

## 6. Worker (Fallback)

If the Vercel bundle exceeds 250 MB or you prefer continuous polling, run the worker locally:

```bash
python -m app.worker
```

For persistent hosting, deploy the worker to [Railway](https://railway.app) or [Fly.io](https://fly.io).
