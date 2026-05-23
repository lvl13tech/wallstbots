-- ============================================================================
-- Level 13 — Referral System Migration
-- Run in Supabase SQL Editor AFTER schema.sql and user_tracker_migration.sql
-- Date: 2026-05-19
-- ============================================================================
-- What this adds:
--   1. referral_redemptions  — records every successful referral (who referred whom,
--                              discount given, credit issued)
--   2. credit_transactions   — full audit trail of every credit earned or applied
--   3. referral_discount_*   — columns on users so we know what promo was applied
--   4. Fixes referral code format → L13-XXXXXXXX (cleaner branding)
--   5. Updates pricing comments throughout
-- ============================================================================


-- ============================================================================
-- 1. USERS TABLE — add referral intake columns
-- ============================================================================

-- Track what discount the NEW subscriber received when they signed up via a referral
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS referral_discount_type    VARCHAR(20),   -- 'half_month' | 'year_20pct'
    ADD COLUMN IF NOT EXISTS referral_discount_applied BOOLEAN NOT NULL DEFAULT FALSE;

-- Update the credit balance column comment (was $75, corrected to $35 per referral)
COMMENT ON COLUMN users.referral_credit_balance
    IS '$35 credit earned per successful referral. Deducted from next autobill.';


-- ============================================================================
-- 2. REFERRAL REDEMPTIONS TABLE
-- One row per successful referral (new subscriber pays → redemption created)
-- ============================================================================

CREATE TABLE IF NOT EXISTS referral_redemptions (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The referral code that was used
    referral_code       VARCHAR(20)     NOT NULL REFERENCES referral_codes(code) ON DELETE RESTRICT,

    -- Who earned the credit (the existing subscriber who shared the code)
    referrer_user_id    UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- The brand-new subscriber who used the code
    new_user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- What discount the new subscriber received
    -- 'half_month'  = 50% off first month  (saves $40.00 on $79.99)
    -- 'year_20pct'  = 20% off annual        (saves $159.80 on $799.00)
    discount_type       VARCHAR(20)     NOT NULL,
    discount_amount     DECIMAL(10, 2)  NOT NULL,   -- dollar value of the discount

    -- Referrer credit
    credit_amount       DECIMAL(10, 2)  NOT NULL DEFAULT 35.00,
    credit_issued       BOOLEAN         NOT NULL DEFAULT FALSE,
    credit_issued_at    TIMESTAMPTZ,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Prevent duplicate redemptions (one code per new user)
    UNIQUE (new_user_id)
);

CREATE INDEX IF NOT EXISTS idx_referral_redemptions_code
    ON referral_redemptions(referral_code);

CREATE INDEX IF NOT EXISTS idx_referral_redemptions_referrer
    ON referral_redemptions(referrer_user_id);

CREATE INDEX IF NOT EXISTS idx_referral_redemptions_new_user
    ON referral_redemptions(new_user_id);


-- ============================================================================
-- 3. CREDIT TRANSACTIONS TABLE
-- Full double-entry ledger of every credit event for every user.
-- Positive amount = credit added; negative = credit applied to a bill.
-- ============================================================================

CREATE TABLE IF NOT EXISTS credit_transactions (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Dollar value. Positive = credit earned. Negative = applied to bill.
    amount                  DECIMAL(10, 2)  NOT NULL,

    -- 'referral_earned'    — referrer earned $35 because someone used their code
    -- 'signup_discount'    — new subscriber got their discount recorded as a credit
    -- 'billing_applied'    — credit was deducted from an autobill
    type                    VARCHAR(30)     NOT NULL,

    description             TEXT,

    -- Link back to the redemption event (nullable for billing_applied rows)
    referral_redemption_id  UUID            REFERENCES referral_redemptions(id) ON DELETE SET NULL,

    -- For billing_applied rows — which subscription period this covered
    billing_period_start    DATE,
    billing_period_end      DATE,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user
    ON credit_transactions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_type
    ON credit_transactions(type);


-- ============================================================================
-- 4. UPDATE referral_codes TRIGGER — nicer L13- prefix
-- Old codes: REF_abcd1234
-- New codes: L13-ABCD1234
-- Only affects NEW users going forward; existing codes remain valid.
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_referral_code()
RETURNS TRIGGER AS $$
BEGIN
    NEW.referral_code = 'L13-' || UPPER(SUBSTRING(MD5(NEW.id::text || NOW()::text), 1, 8));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger already exists from schema.sql — replace is handled by OR REPLACE above.


-- ============================================================================
-- 5. GRANTS for API layer
-- ============================================================================

GRANT SELECT, INSERT, UPDATE ON referral_redemptions  TO "authenticated";
GRANT SELECT, INSERT         ON credit_transactions    TO "authenticated";

-- Service role needs UPDATE on users.referral_credit_balance
GRANT UPDATE ON users TO "authenticated";


-- ============================================================================
-- 6. ROW LEVEL SECURITY
-- Users can only see their own referral data.
-- ============================================================================

ALTER TABLE referral_redemptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_transactions  ENABLE ROW LEVEL SECURITY;

-- Referral redemptions: referrer or new user can see their own rows
CREATE POLICY rr_select_own ON referral_redemptions
    FOR SELECT USING (
        auth.uid() = referrer_user_id OR auth.uid() = new_user_id
    );

-- Credit transactions: user can see their own
CREATE POLICY ct_select_own ON credit_transactions
    FOR SELECT USING (auth.uid() = user_id);


-- ============================================================================
-- 7. CONVENIENCE VIEW — referral stats per user (used by /account/referral)
-- ============================================================================

CREATE OR REPLACE VIEW user_referral_stats AS
SELECT
    u.id                                    AS user_id,
    u.referral_code,
    u.referral_credit_balance,
    COUNT(rr.id)                            AS total_redemptions,
    COALESCE(SUM(rr.credit_amount), 0)      AS total_credits_earned,
    MAX(rr.created_at)                      AS last_redemption_at
FROM users u
LEFT JOIN referral_redemptions rr ON rr.referrer_user_id = u.id AND rr.credit_issued = TRUE
GROUP BY u.id, u.referral_code, u.referral_credit_balance;

GRANT SELECT ON user_referral_stats TO "authenticated";


-- ============================================================================
-- DONE
-- ============================================================================
-- After running this migration, redeploy Backend/main.py to Cloud Run.
-- No data loss. All changes are additive (ADD COLUMN IF NOT EXISTS).
-- ============================================================================
