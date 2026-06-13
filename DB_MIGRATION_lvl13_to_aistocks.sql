-- ============================================================
-- DATABASE MIGRATION: lvl13 → aistocks
-- Run this ONCE after deploying the updated backend code.
-- ============================================================

-- STEP 1: Add 'aistocks' to the enum type
-- (Cannot be inside a transaction, must run first on its own)
ALTER TYPE bot_platform ADD VALUE IF NOT EXISTS 'aistocks';

-- STEP 2: Now migrate the data
-- Run everything below as a separate query after step 1 completes

BEGIN;

-- bots table
UPDATE bots
SET platform = 'aistocks'
WHERE platform = 'lvl13';

-- user_platform_subs
UPDATE user_platform_subs
SET platform = 'aistocks'
WHERE platform = 'lvl13';

-- user_stock_picks
UPDATE user_stock_picks
SET platform = 'aistocks'
WHERE platform = 'lvl13';

-- tracker_live_data
UPDATE tracker_live_data
SET platform = 'aistocks'
WHERE platform = 'lvl13';

-- bot_fund_state — no platform column, keyed by bot_id only, no migration needed

-- Verify — all counts should be 0
SELECT 'bots'              AS tbl, COUNT(*) AS remaining_lvl13 FROM bots              WHERE platform = 'lvl13'
UNION ALL
SELECT 'user_platform_subs',       COUNT(*)                    FROM user_platform_subs WHERE platform = 'lvl13'
UNION ALL
SELECT 'user_stock_picks',         COUNT(*)                    FROM user_stock_picks   WHERE platform = 'lvl13'
UNION ALL
SELECT 'tracker_live_data',        COUNT(*)                    FROM tracker_live_data  WHERE platform = 'lvl13';

COMMIT;
