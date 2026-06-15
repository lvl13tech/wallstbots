-- ============================================================================
-- CORRECTIVE Migration: fix origin_platform whitelist for the current model
-- ============================================================================
-- WHY:
--   The original origin_platform_migration.sql used the OLD platform set:
--     CHECK (origin_platform IN ('lvl13', 'bitbot13', 'wallstbots'))
--     and backfilled unknown rows to 'lvl13'.
--   The CURRENT product platforms are:  aistocks, bitbot13, wallstbots.
--   ('lvl13' is the parent landing page — NOT a sales/product platform.)
--   So the old constraint would REJECT a real 'aistocks' origin and ALLOW a
--   non-existent 'lvl13' one.
--
-- WHAT THIS DOES (safe + idempotent — re-runnable, works whether or not the
-- original migration was applied):
--   1. Ensures the column exists.
--   2. Re-labels any legacy 'lvl13' origin rows to 'aistocks' (the migrated
--      successor of the old lvl13 trading site).  *** SEE NOTE BELOW ***
--   3. Backfills NULL/blank origins to 'unknown' (honest — don't guess a site).
--   4. Replaces the CHECK constraint with the current valid set, plus 'unknown'.
--
-- NOTE on step 2: this assumes old rows tagged 'lvl13' were actually the
--   AI/quantum site that is now aistocks. If some 'lvl13' rows were really a
--   different site, adjust before running. If you'd rather not reclassify them,
--   change 'aistocks' on the UPDATE below to 'unknown'.
--
-- RUN THIS IN: Supabase → SQL Editor.  Run RUN_FIRST_origin_platform_TEST.sql
--   first to see the current state before changing anything.
-- ============================================================================

-- 1. Column exists (no-op if already there)
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS origin_platform VARCHAR(20);

-- 2. Drop the old constraint if present (it has the wrong value set)
ALTER TABLE subscriptions
  DROP CONSTRAINT IF EXISTS subscriptions_origin_platform_check;

-- 3. Reclassify legacy 'lvl13' rows to 'aistocks' (its migrated successor).
--    Change 'aistocks' -> 'unknown' here if you prefer not to attribute them.
UPDATE subscriptions
   SET origin_platform = 'aistocks'
 WHERE origin_platform = 'lvl13';

-- 4. Backfill NULL/blank origins to 'unknown' (don't guess a real site)
UPDATE subscriptions
   SET origin_platform = 'unknown'
 WHERE origin_platform IS NULL OR origin_platform = '';

-- 5. Re-add the CHECK with the CURRENT valid set (+ 'unknown' for legacy rows)
ALTER TABLE subscriptions
  ADD CONSTRAINT subscriptions_origin_platform_check
  CHECK (origin_platform IN ('aistocks', 'bitbot13', 'wallstbots', 'unknown'));

-- 6. Index for "count by site" reporting (no-op if it already exists)
CREATE INDEX IF NOT EXISTS idx_subscriptions_origin_platform
  ON subscriptions(origin_platform);

-- Done. Verify with RUN_FIRST_origin_platform_TEST.sql again afterward.
