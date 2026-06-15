-- ============================================================================
-- READ-ONLY TEST — run this FIRST in Supabase SQL Editor.
-- It changes NOTHING. It just tells you the current state so you know what the
-- corrective migration will do (and whether the original migration ran).
-- ============================================================================

-- A) Does the origin_platform column exist yet?
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'subscriptions'
  AND column_name = 'origin_platform';
-- 0 rows  = column does NOT exist (original migration never ran)
-- 1 row   = column exists (original migration ran at least partly)

-- B) Is the OLD check constraint present, and what does it allow?
SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conname = 'subscriptions_origin_platform_check';
-- If definition mentions 'lvl13'  → it's the stale one; the FIX will replace it.

-- C) What origin values currently exist, and how many of each?
--    (Only works if column exists. If A returned 0 rows, skip C.)
SELECT COALESCE(origin_platform, '(null)') AS origin_platform,
       COUNT(*) AS rows
FROM subscriptions
GROUP BY origin_platform
ORDER BY rows DESC;
-- Watch for: any 'lvl13' rows (will be reclassified to 'aistocks' by the FIX),
-- and any NULLs (will become 'unknown').
