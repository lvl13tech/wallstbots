-- ============================================================================
-- social_features_migration.sql
-- WallStBots social layer: display names, leaderboard opt-in, comments
-- Run once in Supabase SQL editor
-- ============================================================================

-- ── 1. Display name (public handle) on users ─────────────────────────────────
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(50) UNIQUE;

-- Index for fast handle lookups / uniqueness checks
CREATE INDEX IF NOT EXISTS idx_users_display_name ON users(display_name);

-- ── 2. Leaderboard opt-in flag on bots ───────────────────────────────────────
ALTER TABLE bots
    ADD COLUMN IF NOT EXISTS public_leaderboard BOOLEAN DEFAULT TRUE;

-- ── 3. Portfolio comments table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_comments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id        UUID NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name  VARCHAR(50) NOT NULL,   -- snapshot at time of posting
    body          TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 1000),
    is_deleted    BOOLEAN DEFAULT FALSE,  -- soft delete
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_bot_id    ON portfolio_comments(bot_id);
CREATE INDEX IF NOT EXISTS idx_comments_user_id   ON portfolio_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_comments_created   ON portfolio_comments(bot_id, created_at DESC);

-- ── 4. Row-level security for comments ───────────────────────────────────────
ALTER TABLE portfolio_comments ENABLE ROW LEVEL SECURITY;

-- Anyone can read non-deleted comments
CREATE POLICY comments_select_public ON portfolio_comments
    FOR SELECT USING (is_deleted = FALSE);

-- Authenticated users can insert their own comments
CREATE POLICY comments_insert_own ON portfolio_comments
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can only soft-delete their own comments
CREATE POLICY comments_update_own ON portfolio_comments
    FOR UPDATE USING (auth.uid() = user_id);

-- ── 5. Grant permissions ─────────────────────────────────────────────────────
GRANT SELECT, INSERT, UPDATE ON portfolio_comments TO "authenticated";
GRANT SELECT ON portfolio_comments TO "anon";

-- ── Done ─────────────────────────────────────────────────────────────────────
-- After running this migration:
--   1. Deploy updated main.py (7 new endpoints)
--   2. Deploy leaderboard.html to all 3 sites
--   3. Users set their @handle from the dashboard account settings
