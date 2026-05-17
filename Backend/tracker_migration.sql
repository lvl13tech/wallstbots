-- Wall St. Bots — Tracker Live Data Migration
-- Run this in Supabase SQL Editor after the initial schema.sql
-- Date: 2026-05-17

-- ============================================================================
-- TRACKER LIVE DATA TABLE
-- Stores the latest state/news/signals/reports pushed by the GCP VM.
-- One row per (data_type, platform) — UPSERT keeps it always current.
-- ============================================================================

CREATE TABLE IF NOT EXISTS tracker_live_data (
    id            SERIAL PRIMARY KEY,
    data_type     VARCHAR(50)  NOT NULL,  -- 'state', 'news', 'signals', 'reports'
    platform      VARCHAR(50)  NOT NULL DEFAULT 'lvl13',
    data          JSONB        NOT NULL,
    pushed_at     TIMESTAMPTZ  DEFAULT NOW()
);

-- Only one live row per type per platform (upsert target)
CREATE UNIQUE INDEX IF NOT EXISTS idx_tracker_live_data_type_platform
    ON tracker_live_data(data_type, platform);

-- Fast lookup by type
CREATE INDEX IF NOT EXISTS idx_tracker_live_data_type
    ON tracker_live_data(data_type);

-- ============================================================================
-- GRANTS — service role already has full access; grant anon read for public
-- ============================================================================

-- Authenticated users can read tracker data (displayed on dashboard)
GRANT SELECT ON tracker_live_data TO authenticated;
GRANT SELECT ON tracker_live_data TO anon;

-- Sequence is only used internally
GRANT USAGE, SELECT ON SEQUENCE tracker_live_data_id_seq TO authenticated;
