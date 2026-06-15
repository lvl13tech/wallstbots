-- Migrate bots from old platform name 'lvl13' to 'aistocks'
-- Run once in Supabase SQL editor
-- Safe to run multiple times (only updates rows that need it)

UPDATE bots
SET platform = 'aistocks'
WHERE platform = 'lvl13';

-- Verify
SELECT platform, COUNT(*) as count
FROM bots
GROUP BY platform
ORDER BY platform;
