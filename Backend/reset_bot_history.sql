-- ============================================================
-- HARD RESET — Bot Performance History
-- Wipes all simulation state so all 5 bots restart from
-- $1,000 × holdings as of today with correct compounding.
-- Run in Supabase SQL Editor before next refresh.
-- ============================================================

-- 1. Wipe per-portfolio bot simulation state (carryover balances)
TRUNCATE TABLE bot_fund_state;

-- 2. Wipe daily performance snapshots
TRUNCATE TABLE bot_performance_snapshots;

-- Done. Next refresh will start all bots fresh from inception.
