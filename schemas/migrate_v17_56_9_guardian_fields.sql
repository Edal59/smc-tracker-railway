-- ============================================================
-- Migration: v17.56.9 Guardian HTF-Gating & Risk Labels
-- ------------------------------------------------------------
-- Adds the following columns to BOTH signals and opportunities:
--   guardian_label   TEXT     full Guardian label, incl. HTF warnings
--                             e.g. "CONTINUATION BUY (HTF COUNTER — STANDBY)"
--   guardian_risk    INTEGER  HTF-gating risk: 0=low, 1=medium, 2=high
--
-- NOTE ON IDEMPOTENCY:
--   SQLite (the Railway runtime DB) does NOT support
--   "ALTER TABLE ... ADD COLUMN IF NOT EXISTS". At runtime these columns
--   are added idempotently by src/database.py::_run_guardian_gate_migration(),
--   which checks PRAGMA table_info() before each ALTER. This script is the
--   canonical reference and is also safe to run manually on a fresh DB
--   (each ADD COLUMN runs once). CREATE INDEX statements are guarded with
--   IF NOT EXISTS so re-running the index section is always safe.
--
--   These fields are OPTIONAL on the wire — v17.56.8 and older payloads omit
--   them and the decoder applies defaults (guardian_label=NULL, guardian_risk=0).
-- ============================================================

-- ── signals table ──
ALTER TABLE signals ADD COLUMN guardian_label TEXT;
ALTER TABLE signals ADD COLUMN guardian_risk INTEGER DEFAULT 0;

-- ── opportunities table ──
ALTER TABLE opportunities ADD COLUMN guardian_label TEXT;
ALTER TABLE opportunities ADD COLUMN guardian_risk INTEGER DEFAULT 0;

-- ── indexes (idempotent) ──
CREATE INDEX IF NOT EXISTS idx_signals_guardian_risk ON signals(guardian_risk);
CREATE INDEX IF NOT EXISTS idx_opportunities_guardian_risk ON opportunities(guardian_risk);
