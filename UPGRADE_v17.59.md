# UPGRADE — v17.59 🚨 EMERGENCY FIX: Inverted Logic During Strong Trends

> **Severity:** EMERGENCY · **DB migration:** ❌ NONE · **Schema change:** ❌ NONE · **Backward compatible:** ✅ YES · **Deploy:** immediately

## Summary

v17.59 is an **emergency fix** for inverted entry logic during strong directional
trends. The Pine indicator now resolves HTF/LTF trend direction with an explicit
**override path**, reports **range-expansion debug** context, and emits an **AMD
velocity** reading (as a % of ATR) plus a derived **strong-trend mode**.

The backend update is intentionally **minimal**: it adds **9 OPTIONAL webhook
fields** that are **IN-MEMORY ONLY**. They are parsed safely, echoed on
`POST /signal`, and surfaced on `GET /latest` — **but they are NOT persisted to
the database**. There is **no schema migration and no schema change**, so this
release can be deployed immediately with zero database risk.

## New Fields (9, all optional, in-memory only)

| Field                  | Type   | Domain / Example            | Default  | Purpose |
|------------------------|--------|-----------------------------|----------|---------|
| `htf_override_active`  | bool   | `0` / `1`                   | `false`  | HTF trend override engaged |
| `ltf_override_active`  | bool   | `0` / `1`                   | `false`  | LTF trend override engaged |
| `htf_trend_final`      | int    | `-1` / `0` / `1`            | `0`      | Final resolved HTF trend direction |
| `ltf_trend_final`      | int    | `-1` / `0` / `1`            | `0`      | Final resolved LTF trend direction |
| `range_anchor_time`    | text   | `"2026-06-06T09:30:00Z"`    | `""`     | Debug anchor timestamp of the active range |
| `range_force_expanded` | bool   | `0` / `1`                   | `false`  | The range was force-expanded |
| `amd_velocity`         | float  | `87.5` (% of ATR)           | `0.0`    | AMD velocity reading |
| `strong_trend_mode`    | text   | `BEARISH` / `BULLISH` / `NONE` | `NONE` | Derived strong-trend context |

Plus: the existing **`amd_state`** field may be sent with a velocity-based value
(e.g. `MARKDOWN`); it continues to be validated/normalized by the existing
`normalize_amd_state` path (no behaviour change).

> **Why in-memory only?** These fields are ephemeral real-time context for the
> frontend HUD (so it can detect "strong trend mode" and avoid inverted entries).
> They mirror the v17.57 PDH/PDL in-memory pattern — no DB columns, no migration.

## Backend Changes

| File | Change |
|------|--------|
| `src/version.py` | `VERSION` → **`v17.59`**; added features `trend_override_logic`, `amd_velocity_detection` (all existing flags preserved); added `normalize_strong_trend_mode` helper (domain `BEARISH`/`BULLISH`/`NONE`, default `NONE`). |
| `src/oie_processor.py` | `normalize_oie_payload` parses the 9 fields (safe parsers) into the record; new `_apply_trend_override_fields(payload, record)` helper; new `decode_v17_59_payload`; the helper is also applied (defaults) in every older decoder for backward compat; `decode_payload` dispatcher routes `version.startswith("v17.59")` first. |
| `src/webhook_server/routes.py` | `_update_latest_signal` snapshot includes the 9 fields; `POST /signal` response echoes the 9 fields; module docstring updated. |
| `app.py` | Startup banner mentions "Trend Override + AMD Velocity". |
| `src/database.py` | **No change** (no migration). |

## API Behaviour

- **`POST /api/v1/signal`** — accepts the 9 new fields (optional) and echoes them
  in the JSON response. Missing/invalid values fall back to safe defaults.
- **`GET /api/v1/latest`** — the in-memory snapshot now includes the 9 fields.
- **`GET /api/v1/health`** — reports `version: v17.59` and the 2 new feature flags.
- **`GET /api/v1/signals`** — **unchanged** (the 9 fields are not persisted, so
  they do not appear in DB-backed signal rows).

## Safe Parsing & Graceful Coercion

All fields use the existing safe parsers (`_to_int`, `_to_float`) and the new
`normalize_strong_trend_mode`, so malformed input never crashes the webhook path:

| Input | Result |
|-------|--------|
| `amd_velocity = "not_a_number"` | `0.0` |
| `htf_trend_final = None` | `0` |
| `htf_override_active = "yes"` | `False` |
| `strong_trend_mode = "sideways"` | `"NONE"` |
| `range_force_expanded = ""` | `False` |

## Backward Compatibility

All prior payload versions (**v17.58 / v17.57 / v17.56.9 / v17.56.8 / v17.56.7 /
legacy**) decode exactly as before; the 9 new fields default to
`false / 0 / 0.0 / "" / "NONE"`. No existing field, endpoint, or DB row is
affected. The signals table schema is unchanged.

## Testing

- **`test_v17_59.py`** — 111 checks, all passing (version flags, 9-field decode,
  dispatcher routing, backward compat across 6 prior versions, graceful coercion,
  domain validation, **in-memory-only schema assertion**, `/health`,
  `POST /signal` echo, `GET /latest` surface).
- Regression: `test_v17_58.py` (155), `test_v17_57.py` (97), `test_v17_56_9.py`
  (66), `test_v17_56_8.py` (53), `test_oie_integration.py` — all passing.

```bash
python3 test_v17_59.py
```

## Deployment

1. Merge the PR (Railway auto-deploys from `main`).
2. **No migration step** — the DB schema is unchanged.
3. Verify `GET /api/v1/health` reports `v17.59` + the 2 new feature flags.

## PR / Merge Order

This release stacks on the existing version chain:

```
#12 → #14 → #16 → #17 → #18 → #19 (v17.59)
```

PR **#19** — `feature/v17.59-emergency-fix` → `feature/v17.58-sequence-state-machine`.
Because this is an emergency fix with no DB risk, it may be fast-tracked to `main`
once the upstream chain is merged.
