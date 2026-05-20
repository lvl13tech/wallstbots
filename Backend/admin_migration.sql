-- ============================================================================
-- Admin & Referral Fix Migration
-- Run this ONCE in Supabase SQL editor
-- Date: 2026-05-20
-- ============================================================================

-- 1. Add max_free_bots column if it doesn't already exist
ALTER TABLE users ADD COLUMN IF NOT EXISTS max_free_bots INT DEFAULT 0;

-- 2. Ensure tracker_live_data has a unique constraint (needed for ON CONFLICT)
--    (Should already exist from tracker_migration.sql, adding IF NOT EXISTS guard)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'tracker_live_data_data_type_platform_key'
    ) THEN
        ALTER TABLE tracker_live_data
        ADD CONSTRAINT tracker_live_data_data_type_platform_key
        UNIQUE (data_type, platform);
    END IF;
END $$;

-- 3. Grant lvl13cs@gmail.com admin role and unlimited free bots
--    This runs AFTER the user has signed up via the app.
UPDATE users
SET role = 'admin', max_free_bots = 999
WHERE email = 'lvl13cs@gmail.com';

-- Verify (should return 1 row)
SELECT id, email, role, max_free_bots, referral_code FROM users WHERE email = 'lvl13cs@gmail.com';

-- 4. Backfill: create referral_codes rows for any users who are missing them
--    (Fixes the FK bug in the original signup flow)
INSERT INTO referral_codes (code, created_by_user_id)
SELECT u.referral_code, u.id
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM referral_codes rc WHERE rc.code = u.referral_code
)
ON CONFLICT (code) DO NOTHING;

-- 5. Add the KING13 promo for yourself as a backup (unlimited, no charge)
INSERT INTO promo_codes (code, code_type, description, discount_amount, max_uses, active)
VALUES ('KING13', 'unlimited', 'Unlimited free access — admin use', 799.00, NULL, TRUE)
ON CONFLICT (code) DO NOTHING;

-- 6. Grant admin access to all three platforms for lvl13cs@gmail.com
INSERT INTO user_platform_subs (user_id, platform, status, provisioned_at)
SELECT u.id, p.platform, 'active', NOW()
FROM users u
CROSS JOIN (VALUES ('lvl13'), ('wallstbots'), ('bitbot13')) AS p(platform)
WHERE u.email = 'lvl13cs@gmail.com'
ON CONFLICT (user_id, platform) DO UPDATE
    SET status = 'active', provisioned_at = NOW();

-- Done
SELECT 'Admin migration complete.' AS result;
