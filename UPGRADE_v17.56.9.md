# v17.56.9 Backend Upgrade Report
## Guardian HTF-Gating & Risk Labels

**Date:** June 5, 2026  
**Version:** v17.56.9  
**Status:** ✅ Complete — All tests passing (66/66 + 53/53 regression + integration)

---

### Overview

v17.56.9 syncs the backend with the new Pine Script Guardian HTF-gating safety
feature by capturing two additional optional fields on every alert payload:

| Field | Type | Description | Default |
|---|---|---|---|
| `guardian_label` | TEXT | Full Guardian label incl. HTF warnings (e.g. `CONTINUATION BUY (HTF COUNTER — STANDBY)`) | `NULL` |
| `guardian_risk` | INTEGER | HTF-gating risk level | `0` |

**Valid `guardian_risk` values:** `0` = low (HTF aligned), `1` = medium (minor
mismatch), `2` = high (counter-trend / STANDBY). Any unknown / out-of-range /
missing value is normalized to the default `0`.

This release is **fully backward compatible** with v17.56.8, v17.56.7 (and
earlier) payloads — missing Guardian fields receive safe defaults
(`guardian_label=NULL`, `guardian_risk=0`).

---

### Changes Summary

#### 1. Single Source of Truth — `src/version.py`
- `VERSION = "v17.56.9"` — used by `app.py`, `/health`, and `GET /signal`.
- Added `"guardian_htf_gating"` to the `FEATURES` list (exposed via `get_features()`).
- New `VALID_GUARDIAN_RISK = (0, 1, 2)`, `DEFAULT_GUARDIAN_RISK = 0`, and the
  `normalize_guardian_risk(value, default=0)` helper — coerces int/str input,
  guards against `bool`, and falls back to the default on out-of-range/invalid
  input.

#### 2. Database Schema Migration
- **New columns on `signals`:** `guardian_label` (TEXT, nullable),
  `guardian_risk` (INTEGER, default `0`).
- **New columns on `opportunities`:** same two columns / defaults.
- **New indexes:** `idx_signals_guardian_risk`, `idx_opportunities_guardian_risk`.
- Runtime migration `_run_guardian_gate_migration()` in `database.py` is
  **idempotent** — it checks `PRAGMA table_info()` before each `ALTER TABLE`
  (SQLite 3.40.x does not support `ADD COLUMN IF NOT EXISTS`), so it is safe to
  re-run on Railway auto-deploy. Reference SQL lives in
  `schemas/migrate_v17_56_9_guardian_fields.sql`.
- Historical rows are backfilled with the column defaults.

#### 3. v17.56.9 Payload Decoder
- `normalize_v17_56_7_payload()` / `normalize_oie_payload()` now also parse
  `guardian_label` (passthrough) and `guardian_risk` (via `normalize_guardian_risk()`).
  The dual-mode format is shared by v17.56.7/56.8/56.9, and `_is_v17_56_7_payload()`
  now also recognizes the `v17.56.9` version prefix.
- New explicit decoder API in `src/oie_processor.py`:
  - `decode_v17_56_9_payload()` — parses the new Guardian fields.
  - `decode_v17_56_8_payload()` / `decode_v17_56_7_payload()` /
    `decode_legacy_payload()` — apply safe Guardian defaults for older payloads.
  - `decode_payload()` — **universal dispatcher** now routes `v17.56.9` first.

#### 4. Backward Compatibility
- v17.56.8 / v17.56.7 payloads (which lack the Guardian fields) decode cleanly
  with `guardian_label=None`, `guardian_risk=0`.
- Existing `test_v17_56_8.py` (53 checks) and `test_oie_integration.py` continue
  to pass unchanged (no regression). The v17.56.8 version-string assertions were
  relaxed to `>= v17.56.8` since `VERSION` is a forward-moving single source of
  truth.

#### 5. Persistence (both pipelines)
- `insert_opportunity()` stores the two new fields on the `opportunities` table
  (version default bumped to `v17.56.9`).
- The legacy bridge (`oie_to_legacy_compact` → `expand_compact_entry` →
  `insert_signal`) carries the fields through (`_guardian_label` / `_guardian_risk`)
  to the `signals` table.

#### 6. API Responses & Filtering
- `/api/v1/signals` and `/api/v1/signals/<id>` use `SELECT *`, so the new columns
  appear automatically in responses.
- `GET /api/v1/signals` gains an optional `?guardian_risk=` filter
  (backed by `get_signals()` / `count_signals()`); the active filters are echoed
  back in the response.

#### 7. Updated API Endpoints
| Endpoint | Method | Change |
|---|---|---|
| `/api/v1/health` | GET | Version → `v17.56.9`; features now include `guardian_htf_gating` |
| `/api/v1/signal` | GET | Version string sourced from `src/version.py` |
| `/api/v1/signal` | POST | Parses + stores `guardian_label` / `guardian_risk` |
| `/api/v1/signals` | GET | New optional filter `?guardian_risk=2`; new fields in rows |

---

### Files Modified / Created
| File | Changes |
|---|---|
| `src/version.py` | VERSION → `v17.56.9`; `guardian_htf_gating` feature; `normalize_guardian_risk()` + constants |
| `schemas/migrate_v17_56_9_guardian_fields.sql` | **NEW** — reference migration script |
| `schemas/schema.sql` | New columns + index on `signals` |
| `schemas/migrate_v17_14_oie.sql` | New columns on `opportunities` CREATE TABLE |
| `src/database.py` | `_run_guardian_gate_migration()`, `insert_signal` cols, `guardian_risk` filter |
| `src/oie_processor.py` | v17.56.9 detection + parsing + `decode_v17_56_9_payload()` + dispatcher |
| `src/oie_database.py` | `insert_opportunity` stores new fields; version default bump |
| `src/tracker/processor.py` | `expand_compact_entry` passthrough of Guardian fields |
| `src/webhook_server/routes.py` | docstring bump; `?guardian_risk=` filter |
| `app.py` | Startup banner mentions Guardian HTF-Gating |
| `test_v17_56_9.py` | **NEW** — full test suite (66 checks) |
| `test_v17_56_8.py` | Version assertions relaxed to `>= v17.56.8` (no functional change) |

---

### Test Results
```
STEP 1:  version.py + guardian_risk normalize ......... ✅
STEP 2:  DB migration adds guardian columns ........... ✅ (idempotent)
STEP 3:  v17.56.9 payload decodes new fields .......... ✅
STEP 4:  v17.56.8 / v17.56.7 backward compat .......... ✅
STEP 5:  decode_payload() universal dispatcher ........ ✅
STEP 6:  Opportunity insert/retrieve roundtrip ........ ✅
STEP 7:  Signal insert/retrieve roundtrip (bridge) .... ✅
STEP 8:  guardian_risk filter on get/count_signals .... ✅
STEP 9:  Three Guardian risk scenarios (0/1/2) ........ ✅
STEP 10: /health returns v17.56.9 + feature ........... ✅
STEP 11: /signals API includes new fields + filter .... ✅
-----------------------------------------------------------
RESULTS: 66 passed, 0 failed
```
Run with: `python3 test_v17_56_9.py` (from repo root).
Regression: `test_v17_56_8.py` → 53/53, `test_oie_integration.py` → all pass.

---

### v17.56.9 Payload Format
```json
{
  "version": "v17.56.9",
  "mode": "EXECUTION",
  "session": "NY",
  "symbol": "EURUSD",
  "direction": "LONG",
  "setup": "A+ SNIPER",
  "poi": 6,
  "align": "COUNTER_TREND",
  "htf_bias": "BEARISH",
  "ltf_bias": "BULLISH",
  "timestamp": "2026-06-05T14:30:00Z",
  "entry": 1.08550,
  "sl": 1.08250,
  "tp": 1.09450,
  "valid": true,
  "amd_state": "MANIPULATION",
  "sniper_today": 3,
  "execution_today": 5,
  "guardian_label": "CONTINUATION BUY (HTF COUNTER — STANDBY)",
  "guardian_risk": 2
}
```

---

### Deployment Notes
- All migrations are **idempotent** and run automatically on startup
  (`init_db()` → `_run_guardian_gate_migration()`), so Railway auto-deploy from
  `main` applies the schema changes with no manual step required.
- No breaking changes — historical records are preserved and backfilled with
  defaults (`NULL` / `0`).
- Stacks on top of v17.56.8 (HUD Sync) → v17.56.7 (Dual Mode Alert System).
  Recommended merge order: PR #12 (v17.56.7) → PR #14 (v17.56.8) → this PR.
