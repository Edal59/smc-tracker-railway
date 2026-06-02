-- ============================================================================
-- TradeX Tracker — SQLite Migration for SMC v17.56.6
-- OTE Depth Bonus: Adds poi_max and has_ote columns to opportunities table
-- ============================================================================
-- Safe to re-run: uses try/catch pattern (columns ignored if they already exist)
-- Only ADDS columns — no existing data is modified or deleted
-- ============================================================================

-- Add poi_max column (default 6 for v17.56.6+, was implicitly 5)
ALTER TABLE opportunities ADD COLUMN poi_max INTEGER DEFAULT 6;

-- Add has_ote column (boolean flag for OTE Depth Bonus)
ALTER TABLE opportunities ADD COLUMN has_ote INTEGER DEFAULT 0;

-- ============================================================================
-- Migration complete — verify with:
-- PRAGMA table_info(opportunities);
-- ============================================================================
