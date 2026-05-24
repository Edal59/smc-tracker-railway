# 🚀 SMC Performance Tracker — Deployment Guide

## Overview

This project uses **GitHub → Railway auto-deploy** pipeline. Every push to the `main` branch automatically triggers a Railway deployment — zero manual intervention required.

| Component | URL |
|-----------|-----|
| **Production** | https://web-production-b63af.up.railway.app |
| **Frontend** | https://smc-tracker-railway-2027.vercel.app |
| **GitHub Repo** | https://github.com/Edal59/smc-tracker-railway |
| **Webhook** | `POST /api/v1/signal` |
| **Health Check** | `GET /api/v1/health` |

---

## How Auto-Deploy Works

```
┌──────────────┐     git push     ┌──────────────┐     auto-deploy    ┌──────────────┐
│  Local Code   │ ───────────────▶ │    GitHub     │ ─────────────────▶ │   Railway    │
│  (your PC)    │                  │  main branch  │                    │  Production  │
└──────────────┘                  └──────────────┘                    └──────────────┘
```

1. **You push code** to `main` branch on GitHub
2. **Railway detects** the push via GitHub webhook integration
3. **Railway builds** using Nixpacks (reads `runtime.txt` + `requirements.txt`)
4. **Railway deploys** with the start command from `railway.json`
5. **Health check** at `/api/v1/health` confirms the new version is live
6. **Old instance** is gracefully shut down (zero-downtime deploy)

---

## Pushing Updates

### Quick Deploy (single command)

```bash
# From the project root
git add -A && git commit -m "feat: your change description" && git push origin main
```

### Recommended Flow (via feature branch + PR)

```bash
# 1. Create a feature branch
git checkout -b feat/your-feature-name

# 2. Make changes, then commit
git add -A
git commit -m "feat: description of changes"

# 3. Push the branch
git push origin feat/your-feature-name

# 4. Create a Pull Request on GitHub
#    - Review changes
#    - Merge into main
#    → Railway auto-deploys on merge
```

### Version Bump Checklist

When updating the Pine Script indicator version (e.g., v17.54 → v17.26):

- [ ] Update `src/config.py` — version string
- [ ] Update `app.py` — startup log version
- [ ] Update `src/decoders.py` — if alert format changed
- [ ] Update `src/oie_processor.py` — if new signal types added
- [ ] Update `templates/settings.html` — alert templates for TradingView
- [ ] Update Pine Script file — add new `.pine` file
- [ ] Update `tradex-frontend/` — if dashboard changes needed
- [ ] Test locally before pushing

---

## Verifying Deployment

### 1. Check Health Endpoint

```bash
curl https://web-production-b63af.up.railway.app/api/v1/health
```

Expected response:
```json
{"status": "ok", "version": "v17.54"}
```

### 2. Check Railway Dashboard

1. Go to [Railway Dashboard](https://railway.com/dashboard)
2. Select the `smc-tracker-railway` project
3. Check the **Deployments** tab for build status

### 3. Check the Settings Page

Visit https://smc-tracker-railway-2027.vercel.app/settings to verify the version number matches.

---

## Rollback Procedures

### Option 1: Revert via Git (Recommended)

```bash
# Find the commit to revert to
git log --oneline -10

# Revert the bad commit
git revert HEAD
git push origin main
# Railway auto-deploys the reverted version
```

### Option 2: Reset to a Specific Commit

```bash
# Find the good commit hash
git log --oneline -10

# Reset to that commit (WARNING: destructive)
git reset --hard <commit-hash>
git push origin main --force
# Railway auto-deploys the older version
```

### Option 3: Railway Dashboard Rollback

1. Go to Railway Dashboard → Deployments
2. Find the last working deployment
3. Click **Redeploy** on that deployment

---

## Railway Configuration

### Environment Variables (set in Railway dashboard)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (auto-set by Railway) |
| `PORT` | Server port (auto-set by Railway) |
| `FLASK_ENV` | `production` |
| `LOG_LEVEL` | `INFO` |

### Build Configuration (`railway.json`)

```json
{
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120",
    "healthcheckPath": "/api/v1/health",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

## Project Structure

```
smc-tracker-railway/
├── app.py                          # Entry point (Railway runs this)
├── railway.json                    # Railway deploy config
├── Procfile                        # Heroku-compatible process file
├── requirements.txt                # Python dependencies
├── runtime.txt                     # Python version
├── .gitignore                      # Git exclusions
├── .env.example                    # Environment template
├── DEPLOYMENT.md                   # This file
│
├── src/                            # Backend source
│   ├── config.py                   # App configuration
│   ├── database.py                 # Database layer
│   ├── decoders.py                 # Alert message decoders
│   ├── oie_processor.py            # OIE signal processor
│   ├── oie_database.py             # OIE database operations
│   ├── dashboard_routes.py         # Dashboard API routes
│   ├── analytics/                  # Analytics modules
│   ├── tracker/                    # Price tracker
│   └── webhook_server/             # Webhook handler (receives TradingView alerts)
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── settings.html               # Contains alert templates
│   ├── opportunities.html
│   └── trades.html
│
├── static/                         # Static assets (CSS/JS)
├── schemas/                        # SQL migration scripts
├── tradex-frontend/                # React/Next.js frontend (Vercel)
├── backups/                        # Version backups
└── smc_premium_discount_*.pine     # Pine Script indicator files
```

---

## TradingView Alert Setup

The indicator fires alerts via `alert()` function calls. Each alert type sends a JSON payload to the webhook:

| Alert Type | TradingView Condition | Description |
|------------|----------------------|-------------|
| Sniper Long | `Sniper Long` | A+ aligned long entry |
| Sniper Short | `Sniper Short` | A+ aligned short entry |
| Retrace Long | `Retrace Long` | Standard retrace long |
| Retrace Short | `Retrace Short` | Standard retrace short |
| Counter Buy | `Counter Buy` | Counter-trend buy |
| Counter Sell | `Counter Sell` | Counter-trend sell |

**Webhook URL:** `https://web-production-b63af.up.railway.app/api/v1/signal`

See the Settings page for copy-paste alert message templates.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Deploy failed | Check Railway build logs for errors |
| Health check failing | Verify `app.py` starts without errors locally |
| Alerts not received | Check webhook URL in TradingView alert settings |
| Database errors | Check `DATABASE_URL` env var in Railway |
| Frontend stale | Vercel deploys separately — check Vercel dashboard |

### Local Development

```bash
# Clone
git clone https://github.com/Edal59/smc-tracker-railway.git
cd smc-tracker-railway

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env with your values

# Run
python app.py
# Server starts at http://localhost:5000
```

---

*Last updated: May 24, 2026 — v17.54*
