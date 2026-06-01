-- Fix numeric field overflow on bot_performance_snapshots
-- DECIMAL(8,4) caps at 9999.9999 — crypto portfolios can exceed this
-- Must drop the view first, alter columns, then recreate the view

DROP VIEW IF EXISTS bot_latest_performance;

ALTER TABLE bot_performance_snapshots
    ALTER COLUMN gain_loss_pct TYPE DECIMAL(18, 4);

ALTER TABLE bot_performance_snapshots
    ALTER COLUMN total_value TYPE DECIMAL(18, 2);

ALTER TABLE bot_performance_snapshots
    ALTER COLUMN entry_cost TYPE DECIMAL(18, 2);

ALTER TABLE bot_performance_snapshots
    ALTER COLUMN gain_loss TYPE DECIMAL(18, 2);

-- Recreate the view identically
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
