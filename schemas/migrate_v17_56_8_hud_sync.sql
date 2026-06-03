-- ============================================================
-- Migration: v17.56.8 HUD Sync + AMD Context + Daily Counters
-- ------------------------------------------------------------
-- Adds the following columns to BOTH signals and opportunities:
--   amd_state        TEXT    market AMD/Wyckoff state
--                            (ACCUMULATION | MANIPULATION | DISTRIBUTION | MARKUP | MARKDOWN)
--   sniper_today     INTEGER count of A+ SNIPER alerts fired today (HUD counter)
--   execution_today  INTEGER count of EXECUTION-mode alerts fired today (HUD counter)
--
-- NOTE ON IDEMPOTENCY:
--   SQLite (the Railway runtime DB) does NOT support
--   "ALTER TABLE ... ADD COLUMN IF NOT EXISTS". At runtime these columns
--   are added idempotently by src/database.py::_run_hud_sync_migration(),
--   which checks PRAGMA table_info() before each ALTER. This script is the
--   canonical reference and is also safe to run manually on a fresh DB
--   (each ADD COLUMN runs once). CREATE INDEX statements are guarded with
--   IF NOT EXISTS so re-running the index section is always safe.
-- ============================================================

-- ── signals table ──
ALTER TABLE signals ADD COLUMN amd_state TEXT DEFAULT 'ACCUMULATION';
ALTER TABLE signals ADD COLUMN sniper_today INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN execution_today INTEGER DEFAULT 0;

-- ── opportunities table ──
ALTER TABLE opportunities ADD COLUMN amd_state TEXT DEFAULT 'ACCUMULATION';
ALTER TABLE opportunities ADD COLUMN sniper_today INTEGER DEFAULT 0;
ALTER TABLE opportunities ADD COLUMN execution_today INTEGER DEFAULT 0;

-- ── indexes (idempotent) ──
CREATE INDEX IF NOT EXISTS idx_signals_amd_state ON signals(amd_state);
CREATE INDEX IF NOT EXISTS idx_opportunities_amd_state ON opportunities(amd_state);
