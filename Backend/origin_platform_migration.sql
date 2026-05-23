-- ============================================================================
-- Migration: add origin_platform column to subscriptions
-- ============================================================================
-- Purpose:
--   Track which Level 13 site placed each sale (lvl13 / bitbot13 / wallstbots).
--   A sale on ANY site still counts as a sale for the user across ALL sites
--   (since subscriptions are keyed on user_id), but we need to be able to
--   answer "how many sales came from each site this month?" for ops + ads.
--
-- Safe to run multiple times: uses IF NOT EXISTS.
-- ============================================================================

ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS origin_platform VARCHAR(20);

-- Backfill any existing rows with a default so they aren't NULL forever.
UPDATE subscriptions
   SET origin_platform = 'lvl13'
 WHERE origin_platform IS NULL;

-- Index for the obvious aggregate query ("count by site")
CREATE INDEX IF NOT EXISTS idx_subscriptions_origin_platform
  ON subscriptions(origin_platform);

-- Sanity check: cap to known values via a CHECK constraint.
-- (Done as a do-block so it's idempotent.)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'subscriptions_origin_platform_check'
  ) THEN
    ALTER TABLE subscriptions
      ADD CONSTRAINT subscriptions_origin_platform_check
      CHECK (origin_platform IN ('lvl13', 'bitbot13', 'wallstbots'));
  END IF;
END$$;
