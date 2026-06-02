-- ============================================================
-- Migration: v17.56.7 Dual Mode Alert System
-- Adds mode, session_tag, valid columns to opportunities table
-- Adds mode, session_tag, valid columns to signals table
-- ============================================================

-- Opportunities table: add mode column
ALTER TABLE opportunities ADD COLUMN mode TEXT DEFAULT 'DATA';
-- Opportunities table: add session_tag column  
ALTER TABLE opportunities ADD COLUMN session_tag TEXT DEFAULT 'NY';
-- Opportunities table: add valid column
ALTER TABLE opportunities ADD COLUMN valid INTEGER DEFAULT 1;

-- Signals table: add mode column
ALTER TABLE signals ADD COLUMN mode TEXT DEFAULT 'DATA';
-- Signals table: add session_tag column
ALTER TABLE signals ADD COLUMN session_tag TEXT DEFAULT 'NY';
-- Signals table: add valid column
ALTER TABLE signals ADD COLUMN valid INTEGER DEFAULT 1;

-- Index for efficient mode/session filtering
CREATE INDEX IF NOT EXISTS idx_opportunities_mode ON opportunities(mode);
CREATE INDEX IF NOT EXISTS idx_opportunities_session_tag ON opportunities(session_tag);
CREATE INDEX IF NOT EXISTS idx_opportunities_valid ON opportunities(valid);
CREATE INDEX IF NOT EXISTS idx_signals_mode ON signals(mode);
CREATE INDEX IF NOT EXISTS idx_signals_session_tag ON signals(session_tag);
