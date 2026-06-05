# Upgrade Notes — v17.57: PDH/PDL Institutional Liquidity Levels

## Overview

v17.57 adds support for **Previous Day High / Previous Day Low (PDH/PDL)
institutional liquidity levels** in the OIE webhook payload. These are
ephemeral daily reference levels used by the indicator to flag proximity to,
and sweeps of, the prior day's range.

Crucially, these six new fields are **in-memory only** — they are deliberately
**NOT persisted** to the SQLite database. PDH/PDL are recomputed every trading
day and only matter for the most recent signal, so there is **no schema change
and no migration** in this release. The latest values are surfaced via a new
lightweight `GET /latest` endpoint and echoed in the `POST /signal` response.

## New Fields

| Field        | Type  | Source         | Default | Meaning                                            |
|--------------|-------|----------------|---------|----------------------------------------------------|
| `pdh`        | float | `pdh`          | `0.0`   | Previous Day High price                            |
| `pdl`        | float | `pdl`          | `0.0`   | Previous Day Low price                             |
| `near_pdh`   | bool  | `near_pdh` 0/1 | `False` | Price within 15% of the PDH–PDL range from the PDH |
| `near_pdl`   | bool  | `near_pdl` 0/1 | `False` | Price within 15% of the PDH–PDL range from the PDL |
| `pdh_swept`  | bool  | `pdh_swept` 0/1| `False` | PDH has been swept (liquidity raid above)          |
| `pdl_swept`  | bool  | `pdl_swept` 0/1| `False` | PDL has been swept (liquidity raid below)          |

The booleans arrive as integer `0`/`1` from Pine Script and are coerced to
Python `bool`. Prices arrive as floats. All values are parsed with the existing
safe coercion helpers (`_to_float`, `_to_int`), so malformed input
(`"invalid"`, `null`, `""`) degrades gracefully to the defaults above rather
than raising.

### Example v17.57 payload

```json
{
  "version": "v17.57",
  "mode": "EXECUTION", "session": "NY", "symbol": "EURUSD",
  "direction": "LONG", "setup": "A+ SNIPER", "poi": 7,
  "entry": 1.0855, "sl": 1.0825, "tp": 1.0945, "valid": true,
  "pdh": 1.0823, "pdl": 1.0791,
  "near_pdh": 0, "near_pdl": 1,
  "pdh_swept": 0, "pdl_swept": 1
}
```

> Indicator-side note: the Pine v17.57 indicator raises the POI maximum from 6
> to 7 and grants a +1 POI bonus when `near_pdh`/`near_pdl` is set. The backend
> already handles a dynamic POI denominator via `parse_poi_field` (`poi_max`
> from the payload), so no backend change was required for that.

## Changes

### 1. `src/version.py`
- `VERSION` bumped to `v17.57`.
- Added `"pdh_pdl_liquidity"` to the feature list (all prior features retained).
- No new helper constants needed — PDH/PDL use generic safe parsers.

### 2. `src/oie_processor.py` (decoder)
- New helper `_apply_pdh_pdl_fields(payload, record)` parses the six fields
  into the record (`pdh`/`pdl` via `_to_float(..., 0.0)`, the four flags via
  `bool(_to_int(..., 0))`). Calling it on an older payload simply applies the
  defaults — this is how backward compatibility is guaranteed.
- New `decode_v17_57_payload(payload)` — runs `decode_v17_56_9_payload` then
  applies the PDH/PDL fields.
- `_apply_pdh_pdl_fields` is also invoked by every other decoder
  (`decode_v17_56_9/8/7_payload`, `decode_legacy_payload`) so **all** records
  carry the six fields regardless of payload version.
- `decode_payload` dispatcher gains a `v17.57` branch (first match).
- `normalize_oie_payload` (the live webhook path) parses the six fields into
  its result dict, and `_is_v17_56_7_payload` now recognises `v17.57`.

### 3. `src/webhook_server/routes.py` (API)
- Module-level in-memory cache `_LATEST_SIGNAL` + `_update_latest_signal()`
  helper storing a curated snapshot (incl. PDH/PDL, excl. raw payload).
- `POST /api/v1/signal` updates the cache after `insert_opportunity` and now
  echoes the six PDH/PDL fields in its JSON response.
- New `GET /api/v1/latest` (auth-protected) returns
  `{"signal": <snapshot|null>, "version": "v17.57"}` — the canonical way to
  read the ephemeral PDH/PDL levels.

### 4. `app.py`
- Startup banner now lists "PDH/PDL Liquidity".

## In-Memory-Only Rationale (No DB Migration)

PDH/PDL are **daily reference levels** that change every session and are only
meaningful for the current/most-recent signal. Persisting them per-row would
add columns that are stale the moment the day rolls over. Instead:

- `insert_signal` / `insert_opportunity` write only their fixed column lists, so
  the six extra keys in the record dict are silently ignored at the DB layer —
  they flow purely in memory.
- The most-recent snapshot lives in `_LATEST_SIGNAL` and is exposed via
  `GET /latest`. It resets on process restart (acceptable — PDH/PDL are
  re-sent with every signal).
- **No `schema.sql`, migration, or database module was touched.**

## Backward Compatibility

- v17.56.9 / v17.56.8 / v17.56.7 / legacy payloads decode unchanged; the six
  PDH/PDL fields default to `0.0` / `False`.
- All previously-supported fields (Guardian, HUD-sync AMD, daily counters,
  dual-mode) are still parsed exactly as before.
- `/signals` (DB-backed) is unaffected and contains no PDH/PDL columns.

## API Changes Summary

| Endpoint            | Change                                                            |
|---------------------|-------------------------------------------------------------------|
| `GET /health`       | Reports `v17.57` + `pdh_pdl_liquidity` feature (automatic).        |
| `POST /signal`      | Response now echoes `pdh/pdl/near_pdh/near_pdl/pdh_swept/pdl_swept`.|
| `GET /latest` (new) | Returns the in-memory snapshot of the most recent signal + PDH/PDL.|
| `GET /signals`      | Unchanged; PDH/PDL not present (in-memory only).                  |

## Files Modified

| File                              | Change                                             |
|-----------------------------------|----------------------------------------------------|
| `src/version.py`                  | VERSION → v17.57; add `pdh_pdl_liquidity` feature  |
| `src/oie_processor.py`            | PDH/PDL parsing, helper, `decode_v17_57_payload`, dispatcher |
| `src/webhook_server/routes.py`    | In-memory cache, `/latest`, POST response fields   |
| `app.py`                          | Startup banner                                     |
| `test_v17_57.py` (new)            | 97-check test suite                                |
| `test_v17_56_9.py`                | Relax 3 version-string asserts to `>=` (forward-compat) |

## Test Results

```
test_v17_57.py ............... 97 passed, 0 failed
test_v17_56_9.py .............. 66 passed, 0 failed
test_v17_56_8.py .............. 53 passed, 0 failed
test_oie_integration.py ....... ALL INTEGRATION TESTS PASSED
```

## Deployment Notes

This branch (`feature/v17.57-pdh-pdl-levels`) is **stacked** on the v17.56.9
branch. Railway auto-deploys from `main`, so the stacked PRs must be merged in
order:

```
PR #12 (v17.56.7, base main)
  └─ PR #14 (v17.56.8)
       └─ PR #16 (v17.56.9)
            └─ PR (v17.57, this branch)   ← merge last
```

No database migration runs on deploy for this release — PDH/PDL are in-memory
only.
