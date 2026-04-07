# 📊 SMC Performance Tracker — Cloud Edition

A cloud-deployed webhook server and performance dashboard for tracking Smart Money Concept (SMC) trading signals from TradingView.

**No local setup needed. Always online. Permanent webhook URL.**

## ✨ Features

- **🔗 Webhook Server** — Receives TradingView alerts via HTTP POST
- **📊 Web Dashboard** — Browser-based performance analytics
- **📋 Trade Log** — Full signal history with detail view
- **📈 Metrics** — Win rate, expectancy, profit factor, Sharpe ratio, drawdown
- **🔒 API Key Auth** — Secure webhook with API key in request body
- **📊 Breakdowns** — Performance by session, direction, POI score, kill zone
- **📉 P&L Curve** — Cumulative R:R chart
- **📤 CSV Export** — Export signals data

---

## 🚀 Deploy to Railway (5 minutes)

### Step 1: Push to GitHub

```bash
# Clone this repo or push to your GitHub
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/smc-tracker.git
git push -u origin main
```

### Step 2: Deploy on Railway

1. Go to [railway.com](https://railway.com) and sign up (free tier available)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `smc-tracker` repository
4. Railway will auto-detect Python and deploy

### Step 3: Set Environment Variables

In Railway dashboard → your project → **Variables** tab:

| Variable | Value | Required |
|----------|-------|----------|
| `SMC_API_KEY` | `your-secret-api-key` | ✅ Yes |
| `REQUIRE_AUTH` | `true` | ✅ Yes |
| `LOG_LEVEL` | `INFO` | Optional |
| `PRICE_TRACKER_ENABLED` | `false` | Optional |

> 💡 Railway automatically sets `PORT` — don't set it manually.

### Step 4: Get Your Webhook URL

After deployment, Railway gives you a URL like:
```
https://smc-tracker-production.up.railway.app
```

Your webhook URL will be:
```
https://smc-tracker-production.up.railway.app/api/v1/signal
```

### Step 5: Configure TradingView

1. In TradingView, create an alert
2. Set **Webhook URL** to your Railway URL + `/api/v1/signal`
3. Set the **Alert Message** to include your API key:

```json
{
  "api_key": "your-secret-api-key",
  "event": "{{strategy.order.action}}",
  "pair": "{{ticker}}",
  "direction": "{{strategy.order.action}}",
  "entry_price": {{close}},
  "signal_id": "{{ticker}}_{{timenow}}_{{strategy.order.action}}"
}
```

4. Click **Create** ✅

---

## 🖥️ Dashboard

Visit your Railway URL in a browser to see:
- **Dashboard** (`/`) — Performance overview, charts, metrics
- **Trade Log** (`/trades`) — All signals with filtering and detail view
- **Setup Guide** (`/settings`) — Webhook URL, API key, templates

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/signal` | Receive webhook signal |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/signals` | List signals (auth required) |
| `GET` | `/api/v1/metrics` | Performance metrics |
| `GET` | `/api/v1/pnl` | P&L curve data |
| `GET` | `/api/v1/report` | Full JSON report |
| `GET` | `/api/v1/export/csv` | CSV export |

**Authentication:** Include `api_key` in JSON body or `X-API-Key` header.

---

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SMC_API_KEY` | *(empty)* | API key for authentication |
| `REQUIRE_AUTH` | `true` | Enable/disable auth |
| `PORT` | `5000` | Server port (Railway sets this) |
| `HOST` | `0.0.0.0` | Bind host |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DATABASE_PATH` | `data/smc_tracker.db` | SQLite database path |
| `PRICE_TRACKER_ENABLED` | `false` | Enable background price tracking |
| `PRICE_PROVIDER` | `mock` | Price provider (mock/twelve_data/alpha_vantage) |
| `PRICE_API_KEY` | *(empty)* | API key for price provider |

---

## 📁 Project Structure

```
smc_tracker_railway/
├── app.py                    # Main entry point (gunicorn uses this)
├── Procfile                  # Railway/Heroku process file
├── requirements.txt          # Python dependencies
├── railway.json              # Railway configuration
├── runtime.txt               # Python version
├── nixpacks.toml             # Nixpacks build config
├── .env.example              # Example environment variables
├── schemas/
│   └── schema.sql            # SQLite database schema
├── templates/
│   ├── base.html             # Base template
│   ├── dashboard.html        # Dashboard page
│   ├── trades.html           # Trade log page
│   └── settings.html         # Setup guide page
├── static/
│   ├── css/style.css         # Dashboard styles
│   └── js/
│       ├── dashboard.js      # Dashboard JavaScript
│       └── trades.js         # Trade log JavaScript
└── src/
    ├── config.py             # Environment-based configuration
    ├── database.py           # SQLite CRUD operations
    ├── dashboard_routes.py   # Web dashboard routes
    ├── webhook_server/
    │   ├── app.py            # Flask app factory
    │   ├── routes.py         # API routes & auth
    │   └── validators.py     # Payload validation
    ├── tracker/
    │   ├── processor.py      # Signal processing
    │   └── price_tracker.py  # Background price tracker
    └── analytics/
        ├── metrics.py        # Performance calculations
        ├── reports.py        # Report generation
        └── aggregator.py     # Daily metrics aggregation
```

---

## ⚠️ Important Notes

- **SQLite on Railway**: Railway uses ephemeral storage — your database resets on redeploy. For persistent data, consider upgrading to Railway's PostgreSQL add-on.
- **Free Tier**: Railway's free tier has usage limits. Check [railway.com/pricing](https://railway.com/pricing).
- **TradingView Pro**: Webhook alerts require TradingView Pro or higher subscription.

---

## 🛠️ Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/smc-tracker.git
cd smc-tracker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SMC_API_KEY=your-key-here
export PORT=5000

# Run
python app.py
# or with gunicorn:
gunicorn app:app --bind 0.0.0.0:5000
```

Visit `http://localhost:5000` for the dashboard.

---

**Built with ❤️ for SMC traders**
