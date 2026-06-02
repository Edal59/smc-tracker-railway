# SMC Tracker v17.56.6 Backend Upgrade Summary

**Date:** 2026-06-01  
**Branch:** `feature/v17.56.6-upgrade`  
**Base:** v17.54.2 backend  

---

## Changes Made

### 1. 🔐 Authentication Fix (401 Resolution)

**Root Cause:** TradingView webhooks send JSON POST bodies without custom headers. The backend only checked `api_key` in the JSON body and `X-API-Key` header. Since Pine Script `alertcondition()` payloads don't include an `api_key` field, all webhooks were rejected with 401.

**Fix:** Extended auth to check 4 sources (in priority order):
1. **JSON body** — `api_key` or `k` field (existing, backward-compatible)
2. **Query parameter** — `?api_key=xxx` (NEW — recommended for TradingView)
3. **X-API-Key header** (existing)
4. **Authorization: Bearer** header (NEW)

**Files changed:**
- `src/webhook_server/routes.py` — `receive_signal()` POST handler + `require_api_key` decorator

**TradingView Setup:**
Set your webhook URL to:
```
https://web-production-b63af.up.railway.app/api/v1/signal?api_key=YOUR_KEY_HERE
```

### 2. 📊 POI Decoder Update (v17.56.6 /6 Support)

**Change:** POI score max updated from /5 to /6 with OTE (Optimal Trade Entry) depth bonus parsing.

**New parser: `parse_poi_field()`**
- Handles integer POI: `5` → `{score: 5, max: 6, has_ote: false}`
- Handles fraction POI: `"4/6"` → `{score: 4, max: 6, has_ote: false}`
- Handles OTE tag: `"5/6 (OTE)"` → `{score: 5, max: 6, has_ote: true}`
- Backward compatible: `"3/5"` → `{score: 3, max: 5, has_ote: false}`

**Files changed:**
- `src/oie_processor.py` — New `parse_poi_field()` function, updated `normalize_oie_payload()`
- `src/oie_database.py` — INSERT includes `poi_max` and `has_ote` columns

### 3. 🔄 CONTINUATION Alert Support

**Change:** Pine Script v17.56.6 renamed "RETRACE LONG/SHORT" alerts to "CONTINUATION LONG/SHORT". Backend now maps both to the same `retrace_long`/`retrace_short` setup types.

**New alert mappings:**
| Alert String | Setup Type |
|---|---|
| `CONTINUATION LONG` | `retrace_long` |
| `CONTINUATION SHORT` | `retrace_short` |
| `CONTINUATION_LONG` | `retrace_long` |
| `CONTINUATION_SHORT` | `retrace_short` |

Old `RETRACE LONG/SHORT` alerts still work (backward compatible).

**Files changed:**
- `src/oie_processor.py` — `_V17_54_ALERT_MAP` extended

### 4. 🗄️ Database Migration

**New columns on `opportunities` table:**

| Column | Type | Default | Purpose |
|---|---|---|---|
| `poi_max` | INTEGER | 6 | Maximum POI score (6 for v17.56.6+) |
| `has_ote` | INTEGER | 0 | OTE Depth Bonus flag (1=true, 0=false) |

**Migration:** Auto-runs on startup via `_run_ote_migration()` in `database.py`. Safe to re-run — checks if columns exist first. No existing data modified.

**Files changed:**
- `src/database.py` — New `_run_ote_migration()` function, called from `init_db()`
- `schemas/migrate_v17_56_6_ote.sql` — SQL migration file

### 5. 📝 Version String Updates

All version references updated from `v17.54.2` to `v17.56.6`:

| Location | File |
|---|---|
| Startup banner | `app.py` |
| Health check endpoint | `src/webhook_server/routes.py` |
| Signal GET response | `src/webhook_server/routes.py` |
| OIE default version | `src/oie_processor.py` |
| DB default version | `src/oie_database.py` |
| Decoders docstring | `src/decoders.py` |
| HTML page titles | `templates/base.html` |
| Dashboard title | `templates/dashboard.html` |
| Settings/setup guide | `templates/settings.html` |
| Alert templates | `templates/settings.html` |
| Test webhook script | `scripts/test_webhook.py` |

### 6. 🌐 Webhook Response Enhancement

The `/api/v1/signal` OIE response now includes:
```json
{
  "status": "ok",
  "pipeline": "oie",
  "opportunity_id": 42,
  "setup_type": "sniper_long",
  "pair": "AUDUSD",
  "kill_zone": "NY AM",
  "rr_ratio": 3.0,
  "poi_score": 5,
  "poi_max": 6,
  "has_ote": true,
  "legacy_signal_id": "AUDUSD_20260601_143000"
}
```

---

## What Was NOT Changed

- ✅ **Database schema** — Only added columns, no existing data modified or deleted
- ✅ **H4 BOS logic** — Untouched (in Pine Script indicator, not in backend)
- ✅ **Kill Zone timestamp logic** — Untouched
- ✅ **UI theme/aesthetics** — Only version strings updated in templates
- ✅ **Legacy signal pipeline** — Fully backward compatible
- ✅ **Existing alert types** — All old alert formats still work

---

## Testing Results

### Auth Tests (7/7 passed)
| # | Test | Expected | Result |
|---|---|---|---|
| 1 | No auth | 401 | ✅ |
| 2 | Query param `?api_key=` | 200 | ✅ |
| 3 | JSON body `api_key` | 200 | ✅ |
| 4 | X-API-Key header | 200 | ✅ |
| 5 | Authorization: Bearer | 200 | ✅ |
| 6 | Wrong key | 401 | ✅ |
| 7 | Health check (no auth) | 200 | ✅ |

### POI Parser Tests (6/6 passed)
| Input | Score | Max | OTE | ✅ |
|---|---|---|---|---|
| `None` | 0 | 6 | false | ✅ |
| `5` | 5 | 6 | false | ✅ |
| `"4/6"` | 4 | 6 | false | ✅ |
| `"5/6 (OTE)"` | 5 | 6 | true | ✅ |
| `"6/6 (OTE)"` | 6 | 6 | true | ✅ |
| `"3/5"` | 3 | 5 | false | ✅ |

### CONTINUATION Alert Tests (4/4 passed)
All four CONTINUATION variants correctly mapped to `retrace_long`/`retrace_short`.

### Full Pipeline Test (1/1 passed)
v17.56.6 CONTINUATION LONG with `"poi": "5/6 (OTE)"` → correctly inserted into DB with `poi_max=6`, `has_ote=1`.
