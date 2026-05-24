-- ─── Email Preferences Migration ─────────────────────────────────────────────
-- Run once against your Supabase/Postgres database.
-- Adds email notification preference columns to the users table.

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS email_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_daily         BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_bot13_alerts  BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_weekly        BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_monthly       BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS email_source        VARCHAR(20) NOT NULL DEFAULT 'both';
  -- email_source values: 'site' (site picks only) | 'portfolio' (own holdings only) | 'both'

-- Index for fast lookup of opted-in users
CREATE INDEX IF NOT EXISTS idx_users_email_enabled ON users(email_enabled) WHERE email_enabled = TRUE;

-- Comments for documentation
COMMENT ON COLUMN users.email_enabled      IS 'Master toggle — FALSE means no emails at all';
COMMENT ON COLUMN users.email_daily        IS 'Daily signals email';
COMMENT ON COLUMN users.email_bot13_alerts IS 'Bot13 trade alert (same-day, when TRADE decision fires)';
COMMENT ON COLUMN users.email_weekly       IS 'Oracle weekly picks (every Monday)';
COMMENT ON COLUMN users.email_monthly      IS 'Wizard monthly picks (1st of each month)';
COMMENT ON COLUMN users.email_source       IS 'site = site picks only, portfolio = own holdings, both = both';
