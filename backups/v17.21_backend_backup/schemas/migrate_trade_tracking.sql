-- Migration: Add manual trade tracking fields to signals table
-- Run this on existing databases to add the new columns

-- Add trade tracking columns (SQLite ADD COLUMN is safe if column already exists - will error but won't corrupt)
ALTER TABLE signals ADD COLUMN trade_status TEXT DEFAULT 'pending' CHECK(trade_status IN ('pending', 'taken', 'missed', 'ignored'));
ALTER TABLE signals ADD COLUMN actual_entry_price REAL;
ALTER TABLE signals ADD COLUMN actual_exit_price REAL;
ALTER TABLE signals ADD COLUMN actual_entry_time TEXT;
ALTER TABLE signals ADD COLUMN actual_exit_time TEXT;
ALTER TABLE signals ADD COLUMN actual_pnl REAL;
ALTER TABLE signals ADD COLUMN trade_notes TEXT;

-- Add index for trade_status
CREATE INDEX IF NOT EXISTS idx_signals_trade_status ON signals(trade_status);
