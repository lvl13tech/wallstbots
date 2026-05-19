-- Wall St. Bots — User Onboarding & Stock Picks Migration
-- Run this in Supabase SQL Editor AFTER schema.sql and tracker_migration.sql
-- Date: 2026-05-18

-- ============================================================================
-- USER STOCK PICKS
-- Stores each user's chosen stocks per platform (max 50).
-- Replaces entire set on save — latest write wins.
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_stock_picks (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform     VARCHAR(20)  NOT NULL DEFAULT 'lvl13',  -- 'lvl13' | 'wallstbots' | 'bitbot13'
    ticker       VARCHAR(20)  NOT NULL,
    company_name VARCHAR(255),
    added_at     TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(user_id, platform, ticker)
);

CREATE INDEX IF NOT EXISTS idx_user_stock_picks_user_platform
    ON user_stock_picks(user_id, platform);

CREATE INDEX IF NOT EXISTS idx_user_stock_picks_ticker
    ON user_stock_picks(ticker);

-- ============================================================================
-- USER PLATFORM SUBSCRIPTIONS
-- Lightweight status tracker per user per platform.
-- Separate from the full billing 'subscriptions' table — this is just
-- "is this user active on this platform?"
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_platform_subs (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform        VARCHAR(20)  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',  -- 'pending' | 'active' | 'cancelled'
    paypal_email    VARCHAR(255),
    provisioned_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(user_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_user_platform_subs_user
    ON user_platform_subs(user_id);

CREATE INDEX IF NOT EXISTS idx_user_platform_subs_status
    ON user_platform_subs(status);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE user_stock_picks ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_platform_subs ENABLE ROW LEVEL SECURITY;

-- Users can only see their own picks
CREATE POLICY user_stock_picks_select_own ON user_stock_picks
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY user_stock_picks_insert_own ON user_stock_picks
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY user_stock_picks_delete_own ON user_stock_picks
    FOR DELETE USING (auth.uid() = user_id);

-- Users can only see their own subscription status
CREATE POLICY user_platform_subs_select_own ON user_platform_subs
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY user_platform_subs_upsert_own ON user_platform_subs
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT SELECT, INSERT, UPDATE, DELETE ON user_stock_picks TO authenticated;
GRANT SELECT, INSERT, UPDATE ON user_platform_subs TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_stock_picks TO service_role;
GRANT SELECT, INSERT, UPDATE ON user_platform_subs TO service_role;
