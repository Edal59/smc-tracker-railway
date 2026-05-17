-- ============================================================================
-- TradeX Tracker — SQLite Migration for SMC v17.21
-- Opportunity Intelligence Engine (OIE) Schema
-- ============================================================================
-- Adapted from PostgreSQL migration to SQLite for Railway deployment.
-- All statements use IF NOT EXISTS for safe re-runs.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. opportunities — Core table tracking every signal from the indicator
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS opportunities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pair            TEXT        NOT NULL,                    -- e.g. "EURUSD", "GBPJPY"
    setup_type      TEXT        NOT NULL,                    -- "sniper_long", "sniper_short", "retrace_long", "retrace_short"
    setup_id        TEXT        DEFAULT 'dynamic',           -- dedup key from Pine Script

    -- Decoded categorical fields (stored as readable strings)
    h4_bias         TEXT        NOT NULL,                    -- "Bullish", "Bearish", "Neutral"
    pd_zone         TEXT        NOT NULL,                    -- "Premium", "Discount", "Equilibrium"
    kill_zone       TEXT        NOT NULL DEFAULT 'Unknown',  -- "London", "NY AM", "NY PM", "Asian", "Off-Session"
    guardian        TEXT        DEFAULT 'Unknown',           -- "Waiting", "Sniper Buy", etc.

    -- Price levels
    entry_price     REAL,                                    -- entry / suggested_entry
    sl_price        REAL,                                    -- stop loss
    tp_price        REAL,                                    -- take profit

    -- Calculated risk metrics
    risk_pips       REAL,                                    -- |entry - SL| in pips
    reward_pips     REAL,                                    -- |TP - entry| in pips
    rr_ratio        REAL,                                    -- reward / risk

    -- Quality scores from indicator
    quality_score   REAL,                                    -- qualityScore (plot_6)
    poi_score       INTEGER,                                 -- poiScore (plot_7)
    confluence      INTEGER,                                 -- confluenceScore (plot_8)
    dt_stage        INTEGER,                                 -- dtStage (plot_9), sniper alerts only

    -- Lifecycle
    status          TEXT        NOT NULL DEFAULT 'identified',  -- identified → active → tp_hit / sl_hit / expired / invalidated
    identified_at   TEXT        NOT NULL DEFAULT (datetime('now')),
    activated_at    TEXT,                                     -- when price reaches entry zone
    closed_at       TEXT,                                     -- when outcome determined

    -- Raw payload for audit
    raw_payload     TEXT,                                     -- JSON string
    version         TEXT        DEFAULT 'v17.21',

    -- Link to legacy signals table (if migrated from existing signal)
    legacy_signal_id TEXT                                     -- FK to signals.signal_id if applicable
);

-- Performance indexes for opportunities
CREATE INDEX IF NOT EXISTS idx_opp_pair         ON opportunities (pair);
CREATE INDEX IF NOT EXISTS idx_opp_kill_zone    ON opportunities (kill_zone);
CREATE INDEX IF NOT EXISTS idx_opp_status       ON opportunities (status);
CREATE INDEX IF NOT EXISTS idx_opp_identified   ON opportunities (identified_at);
CREATE INDEX IF NOT EXISTS idx_opp_setup_type   ON opportunities (setup_type);
CREATE INDEX IF NOT EXISTS idx_opp_pair_status  ON opportunities (pair, status);
CREATE INDEX IF NOT EXISTS idx_opp_kz_status    ON opportunities (kill_zone, status);

-- ----------------------------------------------------------------------------
-- 2. opportunity_outcomes — Tracks what happened to each opportunity
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS opportunity_outcomes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  INTEGER     NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    outcome_type    TEXT        NOT NULL,                    -- "tp_hit", "sl_hit", "partial_tp", "manual_close", "expired", "invalidated"
    price           REAL,                                    -- price at outcome
    pips_captured   REAL,                                    -- actual pips gained/lost
    notes           TEXT,                                    -- optional context
    timestamp       TEXT        NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_outcomes_opportunity  ON opportunity_outcomes (opportunity_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_type          ON opportunity_outcomes (outcome_type);
CREATE INDEX IF NOT EXISTS idx_outcomes_timestamp     ON opportunity_outcomes (timestamp);

-- ----------------------------------------------------------------------------
-- 3. user_executions — Tracks actual trades users take on opportunities
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_executions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  INTEGER     NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
    user_id         TEXT        NOT NULL DEFAULT 'default',  -- external user identifier

    -- Trade details
    entry_price     REAL        NOT NULL,
    sl_price        REAL,
    tp_price        REAL,
    lot_size        REAL,                                    -- position size

    -- Lifecycle
    executed_at     TEXT        NOT NULL DEFAULT (datetime('now')),
    closed_at       TEXT,
    outcome         TEXT,                                    -- "win", "loss", "breakeven", "partial"
    pips            REAL                                     -- actual P&L in pips
);

CREATE INDEX IF NOT EXISTS idx_exec_opportunity ON user_executions (opportunity_id);
CREATE INDEX IF NOT EXISTS idx_exec_user        ON user_executions (user_id);
CREATE INDEX IF NOT EXISTS idx_exec_executed    ON user_executions (executed_at);

-- ----------------------------------------------------------------------------
-- 4. pair_analytics — Aggregated performance stats per pair + session
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pair_analytics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    pair                TEXT        NOT NULL,
    kill_zone           TEXT        NOT NULL DEFAULT 'All',

    -- Aggregate stats
    total_opportunities INTEGER     NOT NULL DEFAULT 0,
    wins                INTEGER     NOT NULL DEFAULT 0,
    losses              INTEGER     NOT NULL DEFAULT 0,
    win_rate            REAL        DEFAULT 0.0,
    avg_pips            REAL        DEFAULT 0.0,
    total_pips          REAL        DEFAULT 0.0,
    best_rr             REAL        DEFAULT 0.0,
    avg_rr              REAL        DEFAULT 0.0,

    -- Metadata
    updated_at          TEXT        NOT NULL DEFAULT (datetime('now')),

    -- One row per pair + kill zone
    UNIQUE(pair, kill_zone)
);

CREATE INDEX IF NOT EXISTS idx_pair_analytics_pair     ON pair_analytics (pair);
CREATE INDEX IF NOT EXISTS idx_pair_analytics_kz       ON pair_analytics (kill_zone);

-- ============================================================================
-- Migration complete — verify with:
-- SELECT name FROM sqlite_master WHERE type='table'
--   AND name IN ('opportunities','opportunity_outcomes','user_executions','pair_analytics');
-- ============================================================================
