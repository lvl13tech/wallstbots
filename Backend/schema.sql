-- Wall St. Bots Unified Platform - Postgres Schema
-- Date: 2026-05-16
-- Purpose: Single source of truth for users, bots, portfolios, referrals, promo codes, payments, tracker state

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE bot_platform AS ENUM ('lvl13', 'bitbot13', 'wallstbots');
CREATE TYPE bot_status AS ENUM ('active', 'paused', 'deleted');
CREATE TYPE promo_code_type AS ENUM ('free_use', 'discount', 'unlimited');
CREATE TYPE user_role AS ENUM ('user', 'admin');
CREATE TYPE payment_status AS ENUM ('pending', 'completed', 'failed', 'refunded');

-- ============================================================================
-- REFERRALS & PROMO CODES (created first to avoid circular dependencies)
-- ============================================================================

CREATE TABLE referral_codes (
    code VARCHAR(12) PRIMARY KEY,
    created_by_user_id UUID,  -- Will be set after users table exists
    used_count INT DEFAULT 0,
    total_referral_credits DECIMAL(10, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- USERS & AUTH
-- ============================================================================

-- Users table (integrates with Supabase Auth via auth.users)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE,
    role user_role DEFAULT 'user',
    full_name VARCHAR(255),

    -- Referral tracking
    referral_code VARCHAR(12) NOT NULL UNIQUE REFERENCES referral_codes(code),
    referred_by_code VARCHAR(12) REFERENCES referral_codes(code),
    referral_credit_balance DECIMAL(10, 2) DEFAULT 0,  -- $75 per successful referral

    -- Admin settings
    max_free_bots INT DEFAULT 0,  -- admin accounts get free bots
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_referral_code ON users(referral_code);

-- Now add the foreign key from referral_codes back to users
ALTER TABLE referral_codes
ADD CONSTRAINT fk_referral_codes_user
FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Promo codes table (for promotions, discounts, unlimited access)
CREATE TABLE promo_codes (
    code VARCHAR(50) PRIMARY KEY,
    code_type promo_code_type NOT NULL,
    description TEXT,

    -- Discount amount
    discount_amount DECIMAL(10, 2),  -- $75 off, for example
    discount_percentage DECIMAL(5, 2),  -- or X% off

    -- Usage limits
    max_uses INT,  -- NULL = unlimited; levelUp13 = 20
    current_uses INT DEFAULT 0,

    -- Eligibility
    for_platform bot_platform,  -- NULL = all platforms
    min_bots_to_qualify INT DEFAULT 1,

    -- Special access
    grants_unlimited_bots BOOLEAN DEFAULT FALSE,  -- for KING13

    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_promo_codes_active ON promo_codes(active);
CREATE INDEX idx_promo_codes_code ON promo_codes(code);

-- ============================================================================
-- BOTS & PORTFOLIOS
-- ============================================================================

CREATE TABLE bots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform bot_platform NOT NULL,
    status bot_status DEFAULT 'active',

    -- Bot metadata
    name VARCHAR(255),
    description TEXT,

    -- Pricing & billing
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Custom tracking
    is_custom_selection BOOLEAN DEFAULT FALSE  -- customer changed default universe
);

CREATE INDEX idx_bots_user_id ON bots(user_id);
CREATE INDEX idx_bots_platform ON bots(platform);
CREATE INDEX idx_bots_user_platform ON bots(user_id, platform);

-- ============================================================================
-- PORTFOLIOS (stocks for wallstbots / coins for bitbot13)
-- ============================================================================

CREATE TABLE bot_holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id UUID NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Asset identifier
    symbol VARCHAR(20) NOT NULL,  -- AAPL, BTC, etc.
    asset_type VARCHAR(20),  -- 'stock', 'crypto'

    -- Allocation
    weight DECIMAL(5, 2),  -- percentage of portfolio
    quantity DECIMAL(18, 8),
    entry_price DECIMAL(18, 8),

    -- Tracking
    added_at TIMESTAMP DEFAULT NOW(),
    removed_at TIMESTAMP
);

CREATE INDEX idx_bot_holdings_bot_id ON bot_holdings(bot_id);
CREATE INDEX idx_bot_holdings_symbol ON bot_holdings(symbol);

-- ============================================================================
-- WALLSTBOTS SPECIFIC: SECTOR-BASED HOLDINGS
-- ============================================================================

CREATE TABLE wallstbots_sector_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id UUID NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Sector
    sector_name VARCHAR(100) NOT NULL,  -- Technology, Healthcare, Finance, etc.

    -- Top 3 by market cap
    top_1_symbol VARCHAR(20),
    top_2_symbol VARCHAR(20),
    top_3_symbol VARCHAR(20),

    -- Top 2 newest IPOs (2024-2026)
    ipo_1_symbol VARCHAR(20),
    ipo_2_symbol VARCHAR(20),

    -- SpaceX special option
    includes_spacex BOOLEAN DEFAULT FALSE,

    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_wallstbots_sector_bot_id ON wallstbots_sector_config(bot_id);

-- ============================================================================
-- TRACKER STATE & PERFORMANCE
-- ============================================================================

CREATE TABLE bot_performance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id UUID NOT NULL REFERENCES bots(id) ON DELETE CASCADE,

    -- Fund value tracking
    snapshot_date DATE NOT NULL,
    snapshot_time TIMESTAMP DEFAULT NOW(),

    total_value DECIMAL(15, 2),  -- current portfolio value
    entry_cost DECIMAL(15, 2),   -- original investment
    gain_loss DECIMAL(15, 2),    -- realized + unrealized
    gain_loss_pct DECIMAL(8, 4),

    -- Strategy specifics (for lvl13)
    strategy_name VARCHAR(50),  -- BOT13, ORACLE, WIZARD, EQUALIZER, TITAN
    trades_executed INT DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bot_performance_bot_id ON bot_performance_snapshots(bot_id);
CREATE INDEX idx_bot_performance_date ON bot_performance_snapshots(snapshot_date);

-- Latest snapshot (view for convenience)
CREATE VIEW bot_latest_performance AS
SELECT DISTINCT ON (bot_id)
    bot_id,
    total_value,
    entry_cost,
    gain_loss,
    gain_loss_pct,
    snapshot_date,
    strategy_name
FROM bot_performance_snapshots
ORDER BY bot_id, snapshot_time DESC;

-- ============================================================================
-- PAYMENTS & SUBSCRIPTIONS
-- ============================================================================

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Subscription details
    bot_count INT NOT NULL,  -- number of bots user has
    subscription_tier VARCHAR(50),  -- 'first_bot', 'additional_bot', 'unlimited'

    annual_price DECIMAL(10, 2),  -- $799 first, $349 each additional
    promo_code_applied VARCHAR(50) REFERENCES promo_codes(code),
    referral_code_applied VARCHAR(12) REFERENCES referral_codes(code),

    -- Final payment amount
    discount_amount DECIMAL(10, 2) DEFAULT 0,
    final_price DECIMAL(10, 2),

    -- Status
    status payment_status DEFAULT 'pending',
    paypal_transaction_id VARCHAR(255),

    renewal_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- ============================================================================
-- PAYPAL WEBHOOK LOG (for debugging/audit)
-- ============================================================================

CREATE TABLE paypal_webhook_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100),
    transaction_id VARCHAR(255),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    amount DECIMAL(10, 2),
    status VARCHAR(50),

    payload JSONB,
    processed_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT
);

CREATE INDEX idx_paypal_webhook_user_id ON paypal_webhook_log(user_id);
CREATE INDEX idx_paypal_webhook_transaction_id ON paypal_webhook_log(transaction_id);

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255),  -- 'bot_created', 'bot_deleted', 'holdings_changed', etc.
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),

    changes JSONB,  -- old values -> new values
    ip_address INET,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE bots ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_performance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can only see their own profile
CREATE POLICY users_select_own ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY users_update_own ON users
    FOR UPDATE USING (auth.uid() = id);

-- Users can only see their own bots
CREATE POLICY bots_select_own ON bots
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY bots_insert_own ON bots
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY bots_update_own ON bots
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY bots_delete_own ON bots
    FOR DELETE USING (auth.uid() = user_id);

-- Users can only see holdings for their own bots
CREATE POLICY bot_holdings_select_own ON bot_holdings
    FOR SELECT USING (
        bot_id IN (
            SELECT id FROM bots WHERE user_id = auth.uid()
        )
    );

-- Similar policies for other tables
CREATE POLICY bot_performance_snapshots_select_own ON bot_performance_snapshots
    FOR SELECT USING (
        bot_id IN (
            SELECT id FROM bots WHERE user_id = auth.uid()
        )
    );

CREATE POLICY subscriptions_select_own ON subscriptions
    FOR SELECT USING (auth.uid() = user_id);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_update_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER bots_update_timestamp
    BEFORE UPDATE ON bots
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER subscriptions_update_timestamp
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

-- Auto-generate referral code for new users
CREATE OR REPLACE FUNCTION generate_referral_code()
RETURNS TRIGGER AS $$
BEGIN
    NEW.referral_code = 'REF_' || SUBSTRING(MD5(NEW.id::text), 1, 8);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_generate_referral_code
    BEFORE INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION generate_referral_code();

-- ============================================================================
-- INITIAL DATA: PROMO CODES
-- ============================================================================

INSERT INTO promo_codes (code, code_type, description, discount_amount, max_uses, active, for_platform)
VALUES
    ('levelUp13', 'free_use', 'Free for friends and testing (20 uses)', 799.00, 20, TRUE, NULL),
    ('KING13', 'unlimited', 'Unlimited free bots for admins', NULL, NULL, TRUE, NULL)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- GRANTS for API layer
-- ============================================================================

-- FastAPI backend needs to read/write most tables
-- This assumes a Supabase service_role key or separate API user
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO "authenticated";
GRANT SELECT, INSERT, UPDATE, DELETE ON bots TO "authenticated";
GRANT SELECT, INSERT, UPDATE, DELETE ON bot_holdings TO "authenticated";
GRANT SELECT ON bot_performance_snapshots TO "authenticated";
GRANT SELECT, INSERT ON subscriptions TO "authenticated";
GRANT SELECT ON promo_codes TO "authenticated";
GRANT SELECT ON referral_codes TO "authenticated";

-- ============================================================================
-- VIEWS FOR REPORTING
-- ============================================================================

-- User dashboard summary
CREATE VIEW user_dashboard_summary AS
SELECT
    u.id as user_id,
    u.email,
    COUNT(b.id) as total_bots,
    SUM(CASE WHEN b.platform = 'lvl13' THEN 1 ELSE 0 END) as lvl13_bots,
    SUM(CASE WHEN b.platform = 'bitbot13' THEN 1 ELSE 0 END) as bitbot13_bots,
    SUM(CASE WHEN b.platform = 'wallstbots' THEN 1 ELSE 0 END) as wallstbots_bots,
    COALESCE(SUM(s.final_price), 0) as total_paid,
    u.referral_credit_balance
FROM users u
LEFT JOIN bots b ON u.id = b.user_id AND b.status = 'active'
LEFT JOIN subscriptions s ON u.id = s.user_id AND s.status = 'completed'
GROUP BY u.id;

-- Promo code usage report
CREATE VIEW promo_code_usage AS
SELECT
    code,
    code_type,
    current_uses,
    max_uses,
    (current_uses::FLOAT / NULLIF(max_uses, 0)) * 100 as usage_percentage,
    active,
    expires_at
FROM promo_codes
ORDER BY code;
