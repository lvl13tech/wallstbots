-- ============================================================================
-- reports_archive_migration.sql
-- Durable daily archive that feeds the monthly bank-statement Reports feature.
--
-- NOTE: the backend also creates this table automatically (CREATE TABLE IF NOT
-- EXISTS) the first time a state/member push archives into it, so running this
-- file by hand is OPTIONAL. It is kept here as the explicit schema of record.
--
-- One row per fund per day:
--   * platform      -- 'wallstbots' | 'aistocks' | 'bitbot13' for public funds,
--                      or 'member' for member portfolio funds.
--   * bot_id        -- all-zero UUID sentinel for public platform funds; the real
--                      portfolio id for member funds.
--   * fund_name     -- bot13 | oracle | wizard | equalizer | titan.
--   * archive_date  -- ET trading date.
--   * total_value / pnl / pnl_pct / day_pnl / day_pct -- that day's numbers.
--   * positions / strategy / trade_log -- JSONB; trade_log holds BOT13's daily trades.
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_fund_archive (
    platform      TEXT        NOT NULL,
    bot_id        UUID        NOT NULL,
    fund_name     TEXT        NOT NULL,
    archive_date  DATE        NOT NULL,
    total_value   NUMERIC(16,2),
    pnl           NUMERIC(16,2),
    pnl_pct       NUMERIC(12,4),
    day_pnl       NUMERIC(16,2),
    day_pct       NUMERIC(12,4),
    positions     JSONB,
    strategy      JSONB,
    trade_log     JSONB,
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (platform, bot_id, fund_name, archive_date)
);

CREATE INDEX IF NOT EXISTS idx_dfa_lookup
    ON daily_fund_archive (platform, bot_id, archive_date);
