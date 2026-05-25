-- ============================================================================
-- Fix: bot_holdings.weight column overflow
-- Problem: weight is DECIMAL(5,2) which caps at 999.99,
--          but we store $1,000 allocations → INSERT fails with numeric overflow
-- Fix: widen to DECIMAL(10,2) to support allocations up to $99,999,999.99
-- ============================================================================

ALTER TABLE bot_holdings
  ALTER COLUMN weight TYPE DECIMAL(10, 2);

-- Verify the change
SELECT column_name, data_type, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_name = 'bot_holdings' AND column_name = 'weight';
