# Upgrade Notes — v17.58: Sequence State Machine & BOS-Anchored Ranges

> ⚠️ **BREAKING CHANGE (indicator side).** The v17.58 Pine Script reworks the
> alert contract around a 5-state institutional sequence and BOS-anchored
> swing ranges. **The Railway backend remains fully backward-compatible** —
> older payloads (v17.57 / v17.56.9 / v17.56.8 / v17.56.7 / legacy) continue to
> work unchanged, with the new fields defaulting safely. The "breaking" part is
> the *indicator's* output schema; the backend gracefully accepts both.

## Overview

v17.58 introduces two related institutional concepts to the OIE webhook payload:

1. **Sequence State Machine** — the indicator now drives a deterministic
   5-state sequence describing how a setup matures:

   | State | Step           | Meaning                                            |
   |-------|----------------|----------------------------------------------------|
   | `0`   | idle           | no active sequence                                 |
   | `1`   | LOCATION       | price is in the HTF Premium/Discount zone          |
   | `2`   | LIQUIDITY      | liquidity has been swept                           |
   | `3`   | DISPLACEMENT   | LTF shift / displacement detected                  |
   | `4`   | MITIGATION     | price returns into the mitigation zone             |
   | `5`   | EXECUTION      | entry trigger fired — sequence complete            |

2. **BOS-Anchored Ranges** — the active Break-of-Structure swing range
   (`high` / `low` / 50% `equilibrium`) and its directional trend.

Unlike the v17.57 PDH/PDL levels (which were **in-memory only**), these 17
fields **ARE persisted** to the SQLite `signals` table, so there **is a schema
migration** in this release (idempotent, runs automatically on deploy).

## New Fields (17)

### Sequence state machine (4)

| Field               | Type | Source                 | Default | Meaning                                  |
|---------------------|------|------------------------|---------|------------------------------------------|
| `sequence_state`    | int  | `sequence_state` 0–5   | `0`     | Current state in the 5-state sequence    |
| `sequence_step`     | text | `sequence_step`        | `NULL`  | Human-readable current step label        |
| `missing_step`      | text | `missing_step`         | `NULL`  | Next/missing step to complete the sequence |
| `sequence_complete` | bool | `sequence_complete` 0/1| `False` | Whether the full 5-state sequence is satisfied |

### BOS-anchored ranges (4)

| Field             | Type  | Source              | Default | Meaning                                |
|-------------------|-------|---------------------|---------|----------------------------------------|
| `bos_range_high`  | float | `bos_range_high`    | `0.0`   | Active BOS swing high                   |
| `bos_range_low`   | float | `bos_range_low`     | `0.0`   | Active BOS swing low                    |
| `bos_equilibrium` | float | `bos_equilibrium`   | `0.0`   | 50% equilibrium of the BOS range        |
| `bos_trend`       | int   | `bos_trend` 1/-1/0  | `0`     | BOS direction: 1=bullish, -1=bearish, 0=none |

### State completion flags (5)

| Field                 | Type | Source                | Default |
|-----------------------|------|-----------------------|---------|
| `state1_location`     | bool | `state1_location` 0/1 | `False` |
| `state2_liquidity`    | bool | `state2_liquidity` 0/1| `False` |
| `state3_displacement` | bool | `state3_displacement` 0/1 | `False` |
| `state4_mitigation`   | bool | `state4_mitigation` 0/1 | `False` |
| `state5_execution`    | bool | `state5_execution` 0/1| `False` |

### Liquidity / shift detection (4)

| Field                   | Type | Source                  | Default |
|-------------------------|------|-------------------------|---------|
| `liquidity_swept`       | bool | `liquidity_swept` 0/1   | `False` |
| `ltf_shift_detected`    | bool | `ltf_shift_detected` 0/1| `False` |
| `displacement_detected` | bool | `displacement_detected` 0/1 | `False` |
| `mitigation_zone`       | bool | `mitigation_zone` 0/1   | `False` |

Booleans arrive as integer `0`/`1` from Pine Script and are coerced to Python
`bool` (stored as `0`/`1` in SQLite, which has no native BOOLEAN). `sequence_state`
is validated to the domain `{0,1,2,3,4,5}` and `bos_trend` to `{1,-1,0}`; out-of-
range or malformed values degrade gracefully to the defaults above rather than
raising, via the existing safe helpers (`_to_float`, `_to_int`) plus the new
`normalize_sequence_state` / `normalize_bos_trend` validators in `src/version.py`.

### Example v17.58 payload

```json
{
  "version": "v17.58",
  "mode": "EXECUTION", "session": "NY", "symbol": "EURUSD",
  "direction": "LONG", "setup": "A+ SNIPER", "poi": 7,
  "entry": 1.0855, "sl": 1.0825, "tp": 1.0945, "valid": true,
  "sequence_state": 5, "sequence_step": "EXECUTION",
  "missing_step": "", "sequence_complete": 1,
  "bos_range_high": 1.0900, "bos_range_low": 1.0800,
  "bos_equilibrium": 1.0850, "bos_trend": 1,
  "state1_location": 1, "state2_liquidity": 1, "state3_displacement": 1,
  "state4_mitigation": 1, "state5_execution": 1,
  "liquidity_swept": 1, "ltf_shift_detected": 1,
  "displacement_detected": 1, "mitigation_zone": 1
}
```

## Database Migration

This release adds **17 columns to the `signals` table** plus two indexes:

- `idx_signals_sequence_state` (on `sequence_state`)
- `idx_signals_sequence_complete` (on `sequence_complete`)

The migration is implemented in
`src/database.py::_run_sequence_state_migration()` and is **idempotent** — it
checks `PRAGMA table_info(signals)` before each `ALTER TABLE ... ADD COLUMN`,
because SQLite (the Railway runtime DB) does **not** support
`ADD COLUMN IF NOT EXISTS`. It is wired into `init_db()` and runs automatically
on every deploy/startup. A canonical reference SQL script lives at
`schemas/migrate_v17_58_sequence_fields.sql`.

**No data loss / no downtime:** existing rows get the column defaults
(`0` / `0.0` / `NULL`); re-running the migration is a no-op.

## API Changes

### New endpoint: `GET /api/v1/sequence-analytics`

Returns the distribution of persisted signals across the 5-state sequence,
the completion count and completion rate. Supports an optional `?pair=` filter.

```json
{
  "version": "v17.58",
  "pair": null,
  "total_signals": 42,
  "sequence_complete": 11,
  "completion_rate_pct": 26.19,
  "state_distribution": {
    "0": {"label": "idle",         "count": 5},
    "1": {"label": "location",     "count": 8},
    "2": {"label": "liquidity",    "count": 7},
    "3": {"label": "displacement", "count": 6},
    "4": {"label": "mitigation",   "count": 5},
    "5": {"label": "execution",    "count": 11}
  }
}
```

### Extended endpoints

- `GET /api/v1/signals` — now accepts `?sequence_state=5` and
  `?sequence_complete=1` filters, and rows now include all 17 persisted fields.
- `POST /api/v1/signal` — response now echoes the sequence/BOS fields.
- `GET /api/v1/latest` — the in-memory snapshot now includes the v17.58 fields.
- `GET /api/v1/health` — advertises the new `sequence_state_machine` and
  `bos_anchored_ranges` feature flags.

## Backward Compatibility

| Payload version | Behaviour                                                            |
|-----------------|----------------------------------------------------------------------|
| v17.58          | All 17 fields parsed and persisted                                   |
| v17.57          | New fields default (0 / 0.0 / NULL / False); PDH/PDL still in-memory  |
| v17.56.9        | New fields default; Guardian fields still parsed                     |
| v17.56.8        | New fields default; AMD/HUD fields still parsed                      |
| v17.56.7        | New fields default; dual-mode fields still parsed                    |
| legacy/v17.25   | New fields default                                                   |

The universal `decode_payload()` dispatcher routes `v17.58*` to the new
`decode_v17_58_payload()` (which layers `_apply_sequence_bos_fields()` on top of
`decode_v17_57_payload()`), and every older decoder also applies the new-field
defaults so they are always present on the record.

## Files Modified

- `src/version.py` — `VERSION` → `v17.58`; added `bos_anchored_ranges` +
  `sequence_state_machine` feature flags; added `normalize_sequence_state` /
  `normalize_bos_trend` validators.
- `src/oie_processor.py` — parse the 17 fields in `normalize_oie_payload`;
  new `_apply_sequence_bos_fields()` helper; new `decode_v17_58_payload()`;
  default-application in all older decoders; new dispatcher branch; threaded
  fields through `oie_to_legacy_compact()`.
- `src/tracker/processor.py` — `expand_compact_entry()` extracts the 17
  `_`-prefixed bridge fields into the persisted record.
- `src/database.py` — `SEQUENCE_STATE_MIGRATION_PATH`;
  `_run_sequence_state_migration()`; wired into `init_db()`; added the 17 columns
  to `insert_signal()` `known_columns`; `sequence_state` / `sequence_complete`
  filters in `get_signals()` / `count_signals()`.
- `src/webhook_server/routes.py` — `/sequence-analytics` endpoint; `/signals`
  filters; `POST /signal` echo; `/latest` cache fields; docstring.
- `app.py` — startup banner.
- `schemas/migrate_v17_58_sequence_fields.sql` — canonical migration reference.
- `test_v17_58.py` — new suite (155 checks).
- `test_v17_57.py` — relaxed 4 hardcoded `== "v17.57"` version asserts to `>=`.

## Test Results

```
test_v17_58.py ........... 155 passed, 0 failed
test_v17_57.py ............ 97 passed, 0 failed
test_v17_56_9.py .......... 66 passed, 0 failed
test_v17_56_8.py .......... 53 passed, 0 failed
test_oie_integration.py ... ALL INTEGRATION TESTS PASSED
```

## Deployment / Merge Order

This PR is **stacked** on the v17.57 PR. Railway auto-deploys from `main`, so
merge the chain **in order** to keep history linear and migrations sequential:

```
#12 (v17.56.7) → #14 (v17.56.8) → #16 (v17.56.9) → #17 (v17.57) → #18 (v17.58)
```

On deploy, `init_db()` runs the idempotent migration automatically — no manual
SQL step is required.
