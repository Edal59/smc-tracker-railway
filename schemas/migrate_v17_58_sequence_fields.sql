-- ============================================================
-- Migration: v17.58 Sequence State Machine & BOS-Anchored Ranges
-- ------------------------------------------------------------
-- Adds the following 17 columns to the signals table (PERSISTED — unlike the
-- v17.57 PDH/PDL levels which are in-memory only):
--
--   Sequence state machine (4):
--     sequence_state     INTEGER  0=idle | 1=LOCATION | 2=LIQUIDITY |
--                                 3=DISPLACEMENT | 4=MITIGATION | 5=EXECUTION
--     sequence_step      TEXT     human-readable current step label
--     missing_step       TEXT     next/missing step to complete the sequence
--     sequence_complete  INTEGER  0/1 — full 5-state sequence satisfied
--
--   BOS-anchored ranges (4):
--     bos_range_high     REAL     active Break-of-Structure swing high
--     bos_range_low      REAL     active Break-of-Structure swing low
--     bos_equilibrium    REAL     50% equilibrium of the BOS range
--     bos_trend          INTEGER  1=bullish | -1=bearish | 0=none
--
--   State completion flags (5):
--     state1_location      INTEGER  0/1
--     state2_liquidity     INTEGER  0/1
--     state3_displacement  INTEGER  0/1
--     state4_mitigation    INTEGER  0/1
--     state5_execution     INTEGER  0/1
--
--   Liquidity / shift detection (4):
--     liquidity_swept        INTEGER  0/1
--     ltf_shift_detected     INTEGER  0/1
--     displacement_detected  INTEGER  0/1
--     mitigation_zone        INTEGER  0/1
--
-- NOTE ON IDEMPOTENCY:
--   SQLite (the Railway runtime DB) does NOT support
--   "ALTER TABLE ... ADD COLUMN IF NOT EXISTS". At runtime these columns
--   are added idempotently by src/database.py::_run_sequence_state_migration(),
--   which checks PRAGMA table_info() before each ALTER. This script is the
--   canonical reference and is also safe to run manually on a fresh DB
--   (each ADD COLUMN runs once). CREATE INDEX statements are guarded with
--   IF NOT EXISTS so re-running the index section is always safe.
--
--   These fields are OPTIONAL on the wire — v17.57 and older payloads omit
--   them and the decoder applies defaults (0 / 0.0 / NULL).
-- ============================================================

-- ── signals table — sequence state machine ──
ALTER TABLE signals ADD COLUMN sequence_state INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN sequence_step TEXT;
ALTER TABLE signals ADD COLUMN missing_step TEXT;
ALTER TABLE signals ADD COLUMN sequence_complete INTEGER DEFAULT 0;

-- ── signals table — BOS-anchored ranges ──
ALTER TABLE signals ADD COLUMN bos_range_high REAL DEFAULT 0;
ALTER TABLE signals ADD COLUMN bos_range_low REAL DEFAULT 0;
ALTER TABLE signals ADD COLUMN bos_equilibrium REAL DEFAULT 0;
ALTER TABLE signals ADD COLUMN bos_trend INTEGER DEFAULT 0;

-- ── signals table — state completion flags ──
ALTER TABLE signals ADD COLUMN state1_location INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN state2_liquidity INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN state3_displacement INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN state4_mitigation INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN state5_execution INTEGER DEFAULT 0;

-- ── signals table — liquidity / shift detection ──
ALTER TABLE signals ADD COLUMN liquidity_swept INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN ltf_shift_detected INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN displacement_detected INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN mitigation_zone INTEGER DEFAULT 0;

-- ── indexes (idempotent) ──
CREATE INDEX IF NOT EXISTS idx_signals_sequence_state ON signals(sequence_state);
CREATE INDEX IF NOT EXISTS idx_signals_sequence_complete ON signals(sequence_complete);
