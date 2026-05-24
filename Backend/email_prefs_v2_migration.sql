-- ─── Email Preferences v2 Migration ──────────────────────────────────────────
-- Run once against your Supabase/Postgres database.
-- Replaces email_source with per-site toggles + adds email_portfolio flag.
-- Safe to run multiple times (IF NOT EXISTS / IF EXISTS guards throughout).

-- 1. Add new per-section preference columns
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS email_portfolio   BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_wallstbots  BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_bitbot13    BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_lvl13       BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Migrate existing email_source data into the new columns
--    'portfolio' → only portfolio on, sites off
--    'site'      → sites on, portfolio off
--    'both'      → everything on (already the default)
UPDATE users SET
  email_portfolio  = CASE WHEN email_source IN ('portfolio','both') THEN TRUE ELSE FALSE END,
  email_wallstbots = CASE WHEN email_source IN ('site','both')      THEN TRUE ELSE FALSE END,
  email_bitbot13   = CASE WHEN email_source IN ('site','both')      THEN TRUE ELSE FALSE END,
  email_lvl13      = CASE WHEN email_source IN ('site','both')      THEN TRUE ELSE FALSE END
WHERE email_source IS NOT NULL;

-- 3. Drop the old email_source column (optional — safe to leave if you prefer)
-- ALTER TABLE users DROP COLUMN IF EXISTS email_source;

-- 4. Comments
COMMENT ON COLUMN users.email_portfolio  IS 'Include user''s personal portfolio signals in daily email';
COMMENT ON COLUMN users.email_wallstbots IS 'Include Wall St. Bots section in daily email';
COMMENT ON COLUMN users.email_bitbot13   IS 'Include BitBot13 (crypto) section in daily email';
COMMENT ON COLUMN users.email_lvl13      IS 'Include Level XIII (AI/quantum) section in daily email';
