# v17.56.8 Backend Upgrade Report
## HUD Sync + AMD Context Awareness + Daily Counters

**Date:** June 3, 2026  
**Version:** v17.56.8  
**Status:** ✅ Complete — All tests passing (53/53)

---

### Overview

v17.56.8 syncs the backend with the new TradingView HUD by capturing three
additional fields on every alert payload:

| Field | Type | Description | Default |
|---|---|---|---|
| `amd_state` | TEXT | Market AMD / Wyckoff state | `ACCUMULATION` |
| `sniper_today` | INTEGER | Count of A+ SNIPER alerts fired today (HUD counter) | `0` |
| `execution_today` | INTEGER | Count of EXECUTION-mode alerts fired today (HUD counter) | `0` |

**Valid `amd_state` values:** `ACCUMULATION`, `MANIPULATION`, `DISTRIBUTION`, `MARKUP`, `MARKDOWN`.
Any unknown / missing value is normalized to the default `ACCUMULATION`.

This release is **fully backward compatible** with v17.56.7 (and earlier)
payloads — missing HUD fields receive safe defaults.

---

### Changes Summary

#### 1. Single Source of Truth — `src/version.py` (NEW)
- `VERSION = "v17.56.8"` — used by `app.py`, `/health`, and `GET /signal`.
- `FEATURES` list, exposed via `get_features()`:
  `dual_mode`, `session_analytics`, `zombie_prevention`, `invalid_classification`,
  `amd_context_awareness`, `hud_sync`, `daily_counters`.
- `VALID_AMD_STATES`, `DEFAULT_AMD_STATE`, and `normalize_amd_state(value, default)`
  helper (case-insensitive, trims whitespace, falls back to default on invalid input).

#### 2. Database Schema Migration
- **New columns on `signals`:** `amd_state` (TEXT, default `'ACCUMULATION'`),
  `sniper_today` (INTEGER, default `0`), `execution_today` (INTEGER, default `0`).
- **New columns on `opportunities`:** same three columns / defaults.
- **New index:** `idx_signals_amd_state`.
- Runtime migration `_run_hud_sync_migration()` in `database.py` is **idempotent**
  — it checks `PRAGMA table_info()` before each `ALTER TABLE` (SQLite 3.40.x does
  not support `ADD COLUMN IF NOT EXISTS`), so it is safe to re-run on Railway
  auto-deploy. Reference SQL lives in `schemas/migrate_v17_56_8_hud_sync.sql`.
- Historical rows are backfilled with the column defaults.

#### 3. v17.56.8 Payload Decoder
- `normalize_v17_56_7_payload()` now also parses `amd_state` / `sniper_today` /
  `execution_today` (the dual-mode format is shared by v17.56.7 and v17.56.8).
- New explicit decoder API in `src/oie_processor.py`:
  - `decode_v17_56_8_payload()` — parses the new HUD fields.
  - `decode_v17_56_7_payload()` — applies safe defaults for older payloads.
  - `decode_legacy_payload()` — defaults for v17.25 / v17.14 / legacy.
  - `decode_payload()` — **universal dispatcher** that routes by `version`.
- `amd_state` is normalized via `normalize_amd_state()`; counters via `_to_int()`.

#### 4. Backward Compatibility
- v17.56.7 payloads (which lack the HUD fields) decode cleanly with
  `amd_state='ACCUMULATION'`, `sniper_today=0`, `execution_today=0`.
- Existing `test_oie_integration.py` continues to pass unchanged (no regression).

#### 5. Persistence (both pipelines)
- `insert_opportunity()` stores the three new fields on the `opportunities` table.
- The legacy bridge (`oie_to_legacy_compact` → `expand_compact_entry` →
  `insert_signal`) carries the fields through to the `signals` table.

#### 6. API Responses & Filtering
- `/api/v1/signals` and `/api/v1/signals/<id>` use `SELECT *`, so the new columns
  appear automatically in responses.
- `GET /api/v1/signals` gains an optional `?amd_state=` filter
  (backed by `get_signals()` / `count_signals()`); the active filters are echoed
  back in the response.

#### 7. Updated API Endpoints
| Endpoint | Method | Change |
|---|---|---|
| `/api/v1/health` | GET | Version → `v17.56.8`; features now include `amd_context_awareness`, `hud_sync`, `daily_counters` |
| `/api/v1/signal` | GET | Version string sourced from `src/version.py` |
| `/api/v1/signal` | POST | Parses + stores `amd_state` / `sniper_today` / `execution_today` |
| `/api/v1/signals` | GET | New optional filter `?amd_state=MANIPULATION`; new fields in rows |

---

### Files Modified / Created
| File | Changes |
|---|---|
| `src/version.py` | **NEW** — VERSION + FEATURES + AMD helpers (single source of truth) |
| `schemas/migrate_v17_56_8_hud_sync.sql` | **NEW** — reference migration script |
| `schemas/schema.sql` | New columns + index on `signals` |
| `schemas/migrate_v17_14_oie.sql` | New columns on `opportunities` CREATE TABLE |
| `src/database.py` | `_run_hud_sync_migration()`, `insert_signal` cols, `amd_state` filter |
| `src/oie_processor.py` | v17.56.8 detection + parsing + explicit decoder API |
| `src/oie_database.py` | `insert_opportunity` stores new fields; version default bump |
| `src/tracker/processor.py` | `expand_compact_entry` passthrough of HUD fields |
| `src/webhook_server/routes.py` | `/health` from `version.py`; `?amd_state=` filter |
| `app.py` | Startup banner uses `VERSION` |
| `test_v17_56_8.py` | **NEW** — full test suite (53 checks) |

---

### Test Results
```
STEP 1: version.py single source of truth ........... ✅
STEP 2: DB migration adds columns (signals + opps) .. ✅ (idempotent)
STEP 3: v17.56.8 payload decodes new fields ......... ✅
STEP 4: v17.56.7 backward compat (defaults) ......... ✅
STEP 5: decode_payload() universal dispatcher ....... ✅
STEP 6: Opportunity insert/retrieve roundtrip ....... ✅
STEP 7: Signal insert/retrieve roundtrip (bridge) ... ✅
STEP 8: /health returns v17.56.8 + features ......... ✅
STEP 9: /signals API includes new fields ............ ✅
-----------------------------------------------------------
RESULTS: 53 passed, 0 failed
```
Run with: `python3 test_v17_56_8.py` (from repo root).

---

### v17.56.8 Payload Format
```json
{
  "version": "v17.56.8",
  "mode": "EXECUTION",
  "session": "NY",
  "symbol": "EURUSD",
  "direction": "LONG",
  "setup": "A+ SNIPER",
  "poi": 6,
  "align": "WITH_TREND",
  "htf_bias": "BULLISH",
  "ltf_bias": "BULLISH",
  "timestamp": "2026-06-03T14:30:00Z",
  "entry": 1.08550,
  "sl": 1.08250,
  "tp": 1.09450,
  "valid": true,
  "amd_state": "MANIPULATION",
  "sniper_today": 3,
  "execution_today": 5
}
```

---

### Deployment Notes
- All migrations are **idempotent** and run automatically on startup
  (`init_db()` → `_run_hud_sync_migration()`), so Railway auto-deploy from `main`
  applies the schema changes with no manual step required.
- No breaking changes — historical records are preserved and backfilled with
  defaults (`ACCUMULATION` / `0` / `0`).
- Stacks on top of v17.56.7 (Dual Mode Alert System).
