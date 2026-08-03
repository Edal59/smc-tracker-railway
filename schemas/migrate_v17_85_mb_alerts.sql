-- ============================================================
-- Migration: v17.85.34 Market Brief (MB) Execution Alerts
-- ------------------------------------------------------------
-- Adds the columns needed to store the 10 live TradingView execution alerts
-- emitted by the SMC PD Pine indicator v17.85.x (MB_EXECUTE / MB_CONTINUE /
-- MB_CT / MB_MACRO / MB_REENTRY / MB_VREVERSAL).  These trades are created via
-- src/mb_processor.py and stored in the existing ``signals`` table so the live
-- tracker, logged trade data, dashboard and analytics all keep working
-- unchanged — this migration is PURELY ADDITIVE (no existing column/row/data
-- is altered or removed).
--
--   Alert routing / lane fields:
--     alert_name        TEXT     exact alert name (e.g. MB_VREVERSAL_LONG)
--     mb_type           TEXT     WITH_TREND | CONTINUATION | COUNTER_TREND |
--                                RE_ENTRY | V_REVERSAL
--     entry_mode        TEXT     entry-mode label string (e.g. "V-Shape-Breakout")
--     entry_source      TEXT     which field the entry came from: entry_price|price
--     confidence        INTEGER  indicator confidence 0-100
--     macro_express     INTEGER  0/1 — macro-express lane
--     fast_lane         INTEGER  0/1 — V-reversal fast lane
--     re_entry          INTEGER  0/1 — re-entry lane
--     displacement_value REAL    displacement magnitude
--     trigger_text      TEXT     ebTrigger narrative
--     narrative         TEXT     ebNarrative
--     location          TEXT     ebLocation
--     bias              TEXT     ebBias
--     mb_action         TEXT     action label (e.g. "BUY NOW", "RE-ENTRY LONG")
--     geometry_valid    INTEGER  0/1 — SL/entry/TP geometry passed validation
--     test_batch        TEXT     optional test-batch label for paper-test isolation
--     raw_payload       TEXT     full raw JSON payload (retained for analysis)
--
-- NOTE ON IDEMPOTENCY:
--   SQLite (the Railway runtime DB) does NOT support
--   "ALTER TABLE ... ADD COLUMN IF NOT EXISTS". At runtime these columns are
--   added idempotently by src/database.py::_run_mb_alerts_migration(), which
--   checks PRAGMA table_info() before each ALTER. This script is the canonical
--   reference and is safe to run once on a fresh DB. CREATE INDEX statements
--   are guarded with IF NOT EXISTS so re-running the index section is safe.
-- ============================================================

-- ── signals table — MB alert routing / lane fields ──
ALTER TABLE signals ADD COLUMN alert_name TEXT;
ALTER TABLE signals ADD COLUMN mb_type TEXT;
ALTER TABLE signals ADD COLUMN entry_mode TEXT;
ALTER TABLE signals ADD COLUMN entry_source TEXT;
ALTER TABLE signals ADD COLUMN confidence INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN macro_express INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN fast_lane INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN re_entry INTEGER DEFAULT 0;
ALTER TABLE signals ADD COLUMN displacement_value REAL DEFAULT 0;
ALTER TABLE signals ADD COLUMN trigger_text TEXT;
ALTER TABLE signals ADD COLUMN narrative TEXT;
ALTER TABLE signals ADD COLUMN location TEXT;
ALTER TABLE signals ADD COLUMN bias TEXT;
ALTER TABLE signals ADD COLUMN mb_action TEXT;
ALTER TABLE signals ADD COLUMN geometry_valid INTEGER DEFAULT 1;
ALTER TABLE signals ADD COLUMN test_batch TEXT;
ALTER TABLE signals ADD COLUMN raw_payload TEXT;

-- ── indexes (idempotent) ──
CREATE INDEX IF NOT EXISTS idx_signals_alert_name ON signals(alert_name);
CREATE INDEX IF NOT EXISTS idx_signals_mb_type ON signals(mb_type);
CREATE INDEX IF NOT EXISTS idx_signals_macro_express ON signals(macro_express);
CREATE INDEX IF NOT EXISTS idx_signals_fast_lane ON signals(fast_lane);
CREATE INDEX IF NOT EXISTS idx_signals_re_entry ON signals(re_entry);
CREATE INDEX IF NOT EXISTS idx_signals_indicator_version ON signals(indicator_version);
CREATE INDEX IF NOT EXISTS idx_signals_test_batch ON signals(test_batch);
