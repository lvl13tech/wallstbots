-- ============================================================================
-- portfolio_shares_migration.sql
-- WallStBots portfolio privacy + sharing system
-- Run once in Supabase SQL editor
-- ============================================================================

-- ── 1. Add is_private flag to bots ───────────────────────────────────────────
-- Portfolios are public by default; owner can flip private at any time
ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT FALSE;

-- ── 2. Portfolio shares table ─────────────────────────────────────────────────
-- Tracks which users have been granted access to a private portfolio
CREATE TABLE IF NOT EXISTS portfolio_shares (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id              UUID NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    shared_by_user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_with_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (bot_id, shared_with_user_id)   -- can't share same portfolio to same user twice
);

CREATE INDEX IF NOT EXISTS idx_shares_bot_id   ON portfolio_shares(bot_id);
CREATE INDEX IF NOT EXISTS idx_shares_with     ON portfolio_shares(shared_with_user_id);
CREATE INDEX IF NOT EXISTS idx_shares_by       ON portfolio_shares(shared_by_user_id);

-- ── 3. Row-level security ─────────────────────────────────────────────────────
ALTER TABLE portfolio_shares ENABLE ROW LEVEL SECURITY;

-- Owner and recipient can both see the share record
CREATE POLICY shares_select ON portfolio_shares
    FOR SELECT USING (
        auth.uid() = shared_by_user_id
        OR auth.uid() = shared_with_user_id
    );

-- Only the portfolio owner can create a share
CREATE POLICY shares_insert ON portfolio_shares
    FOR INSERT WITH CHECK (auth.uid() = shared_by_user_id);

-- Only the portfolio owner can revoke a share
CREATE POLICY shares_delete ON portfolio_shares
    FOR DELETE USING (auth.uid() = shared_by_user_id);

-- ── 4. Permissions ────────────────────────────────────────────────────────────
GRANT SELECT, INSERT, DELETE ON portfolio_shares TO "authenticated";

-- ── Done ─────────────────────────────────────────────────────────────────────
-- After running this migration:
--   1. Deploy updated main.py (new sharing endpoints)
--   2. Frontend will show privacy toggle + share-by-handle UI on portfolio pages
