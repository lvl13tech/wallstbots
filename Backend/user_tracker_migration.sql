-- ============================================================================
-- Wall St. Bots — User Tracker Migration
-- Run in Supabase SQL Editor AFTER onboarding_migration.sql
-- Date: 2026-05-19
-- ============================================================================


-- ============================================================================
-- 1. EXTEND users TABLE
-- Setup token for post-payment account creation email link
-- ============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS setup_token         VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS setup_token_expires TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS setup_completed     BOOLEAN NOT NULL DEFAULT FALSE;


-- ============================================================================
-- 2. EXTEND user_platform_subs TABLE
-- Full subscription lifecycle tracking
-- ============================================================================

ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS paypal_subscription_id VARCHAR(100);
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS paypal_payer_email     VARCHAR(255);
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS inception_date         TIMESTAMPTZ;
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS last_reset_at          TIMESTAMPTZ;
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS expires_at             TIMESTAMPTZ;
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS starting_capital       NUMERIC(12,2);
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS payment_failed_at      TIMESTAMPTZ;
ALTER TABLE user_platform_subs ADD COLUMN IF NOT EXISTS grace_period_ends      TIMESTAMPTZ;

-- Index for webhook lookups by PayPal subscription ID
CREATE INDEX IF NOT EXISTS idx_user_platform_subs_paypal_sub_id
    ON user_platform_subs(paypal_subscription_id);

-- Index for status lookups (finding all active subs nightly)
CREATE INDEX IF NOT EXISTS idx_user_platform_subs_status_platform
    ON user_platform_subs(status, platform);


-- ============================================================================
-- 3. PER-USER TRACKER RESULTS
-- Stores nightly bot simulation output per customer.
-- Structured identically to tracker_live_data but keyed by user_id.
-- The GCP VM writes here after each per-user run.
-- The authenticated /user/tracker/{data_type} endpoint reads from here.
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_tracker_data (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform    VARCHAR(20)  NOT NULL,   -- 'lvl13' | 'wallstbots' | 'bitbot13'
    data_type   VARCHAR(20)  NOT NULL,   -- 'state' | 'news' | 'signals' | 'reports'
    data        JSONB        NOT NULL,
    pushed_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, platform, data_type)
);

CREATE INDEX IF NOT EXISTS idx_user_tracker_data_user_platform
    ON user_tracker_data(user_id, platform);


-- ============================================================================
-- 4. STOCK PICKS HISTORY
-- Archived snapshot of a user's picks when they reset.
-- Preserves their performance at the point of reset so nothing is lost.
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_stock_picks_history (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform         VARCHAR(20)  NOT NULL,
    picks_snapshot   JSONB        NOT NULL,   -- [{ticker, company_name}, ...]
    starting_capital NUMERIC(12,2),
    inception_date   TIMESTAMPTZ,             -- when THIS run started
    reset_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),  -- when user switched away
    final_state      JSONB        -- last known bot performance at reset time (state data_type)
);

CREATE INDEX IF NOT EXISTS idx_user_stock_picks_history_user_platform
    ON user_stock_picks_history(user_id, platform);


-- ============================================================================
-- 5. PAYPAL WEBHOOK LOG (extend for better debugging)
-- ============================================================================

CREATE TABLE IF NOT EXISTS paypal_webhook_log (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type   VARCHAR(100),
    payload      JSONB,
    processed    BOOLEAN      NOT NULL DEFAULT FALSE,
    error        TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- 6. ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE user_tracker_data      ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_stock_picks_history ENABLE ROW LEVEL SECURITY;

-- Users can only read their own tracker results
CREATE POLICY user_tracker_data_select_own ON user_tracker_data
    FOR SELECT USING (auth.uid() = user_id);

-- Only service_role can write tracker results (GCP VM uses service role key)
CREATE POLICY user_tracker_data_service_insert ON user_tracker_data
    FOR ALL USING (auth.role() = 'service_role');

-- Users can read their own history
CREATE POLICY user_stock_picks_history_select_own ON user_stock_picks_history
    FOR SELECT USING (auth.uid() = user_id);

-- Only service_role can write history (backend writes on reset)
CREATE POLICY user_stock_picks_history_service_insert ON user_stock_picks_history
    FOR ALL USING (auth.role() = 'service_role');


-- ============================================================================
-- 7. GRANTS
-- ============================================================================

GRANT SELECT ON user_tracker_data        TO authenticated;
GRANT SELECT ON user_stock_picks_history TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON user_tracker_data        TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_stock_picks_history TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON paypal_webhook_log       TO service_role;
