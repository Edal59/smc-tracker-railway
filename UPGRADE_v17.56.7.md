# v17.56.7 Backend Upgrade Report
## Dual Mode Alert System + Tracker Integrity Upgrade

**Date:** June 2, 2026  
**Version:** v17.56.7  
**Status:** ✅ Complete — All tests passing

---

### Changes Summary

#### 1. Database Schema Migration
- **New columns on `opportunities`:** `mode` (TEXT), `session_tag` (TEXT), `valid` (INTEGER)
- **New columns on `signals`:** `mode` (TEXT), `session_tag` (TEXT), `valid` (INTEGER)
- **Default values for historical data:** `mode='DATA'`, `session_tag='NY'`, `valid=1`
- **New indexes:** `idx_opportunities_mode`, `idx_opportunities_session_tag`, `idx_signals_mode`, `idx_signals_session_tag`
- **Schema update:** `status` CHECK constraint now includes `'INVALID'`
- Migration is idempotent — safe to re-run on existing databases

#### 2. v17.56.7 Payload Decoder
- New `normalize_v17_56_7_payload()` handles dual-mode JSON format
- Detects v17.56.7 via `direction` + `setup` + version fields
- **Direction taken EXACTLY from JSON** — no inference or flipping
- `htf_bias` string values ("BULLISH"/"BEARISH") handled alongside numeric codes
- Full backward compatibility with v17.56.6 payloads (auto-default: mode=DATA, session=NY, valid=true)

#### 3. Trade Classification Fix (CRITICAL)
- Missing `entry`/`sl`/`tp` (value = 0 or null) → `status = "INVALID"` with `rr = 0`, `pnl = 0`
- Previously these would have been classified as `"LOST"` — **fixed**

#### 4. Zombie Trade Prevention
- `valid: false` payloads are logged as informational events but **not stored** as trades
- Returns `{"status": "ignored", "reason": "invalid signal (valid=false)"}` with HTTP 200
- Prevents POI=0 or invalidated zones from creating junk records

#### 5. EXECUTION-Only Performance Stats
- New `GET /api/v1/stats` endpoint — defaults to `mode=EXECUTION`
- Supports `?mode=ALL` for combined stats, `?mode=DATA` for data-only
- `get_performance_summary_filtered()` function in database.py

#### 6. Session-Based Analytics
- New `GET /api/v1/session-performance` endpoint
- Returns London vs NY comparison with win_rate, avg_rr, total_trades, expectancy
- Always filters by `mode=EXECUTION` for accurate performance

#### 7. Updated API Endpoints
| Endpoint | Method | Change |
|---|---|---|
| `/api/v1/health` | GET | Version bumped to v17.56.7, features list added |
| `/api/v1/signal` | POST | v17.56.7 payload support + zombie prevention |
| `/api/v1/signals` | GET | New filters: `?mode=EXECUTION&session=LONDON` |
| `/api/v1/stats` | GET | **NEW** — EXECUTION-only performance stats |
| `/api/v1/session-performance` | GET | **NEW** — London vs NY comparison |

---

### Files Modified
| File | Changes |
|---|---|
| `app.py` | Version bump, new endpoint logging |
| `src/database.py` | Migration function, new columns, filtered queries |
| `src/oie_processor.py` | v17.56.7 normalizer, direction-exact, backward compat |
| `src/oie_database.py` | Insert with mode/session_tag/valid columns |
| `src/tracker/processor.py` | INVALID classification, mode/session passthrough |
| `src/webhook_server/routes.py` | Zombie prevention, session analytics, stats endpoint |
| `schemas/schema.sql` | INVALID added to status CHECK |
| `schemas/migrate_v17_56_7_dual_mode.sql` | **NEW** — migration script |

### Test Results
```
✅ v17.56.7 Normalize — correct parsing of all fields
✅ DB insert — mode/session_tag/valid stored correctly
✅ v17.56.6 backward compat — defaults applied (DATA/NY/true)
✅ Zombie prevention — valid=false → ignored
✅ Legacy bridge — mode/session passed to signals table
✅ INVALID classification — missing EP/SL/TP → INVALID (not LOST)
✅ Direction exact — SHORT taken from JSON, no flipping
✅ Health check — v17.56.7 with features list
✅ Session performance — London vs NY endpoint functional
✅ Stats endpoint — defaults to EXECUTION mode
✅ Signals filter — mode/session query params working
```

### v17.56.7 Payload Format
```json
{
  "version": "v17.56.7",
  "mode": "EXECUTION",
  "session": "LONDON",
  "symbol": "GBPUSD",
  "direction": "LONG",
  "setup": "A+ SNIPER",
  "poi": 6,
  "align": "WITH_TREND",
  "htf_bias": "BULLISH",
  "ltf_bias": "BULLISH",
  "timestamp": "2026-06-02T10:00:00Z",
  "entry": 1.34195,
  "sl": 1.33800,
  "tp": 1.35385,
  "valid": true
}
```

### Deployment Ready
- All migrations are idempotent (safe for Railway auto-deploy)
- No breaking changes to existing data
- Historical records preserved with default values
