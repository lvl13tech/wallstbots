-- ============================================================
-- Fix bot_fund_state column precision
-- NUMERIC(14,2) and NUMERIC(10,4) are too small for crypto
-- portfolios and long-term compounding gains/losses.
-- Run in Supabase SQL Editor.
-- ============================================================

ALTER TABLE bot_fund_state
    ALTER COLUMN total_value   TYPE NUMERIC(18, 2),
    ALTER COLUMN entry_cost    TYPE NUMERIC(18, 2),
    ALTER COLUMN gain_loss     TYPE NUMERIC(18, 2),
    ALTER COLUMN gain_loss_pct TYPE NUMERIC(18, 4),
    ALTER COLUMN day_pnl       TYPE NUMERIC(18, 2),
    ALTER COLUMN day_pct       TYPE NUMERIC(18, 4);
