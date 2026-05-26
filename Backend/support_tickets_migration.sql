-- ============================================================================
-- Support Tickets Table
-- Run in Supabase SQL Editor
-- ============================================================================

CREATE TABLE IF NOT EXISTS support_tickets (
  id            BIGSERIAL PRIMARY KEY,
  ticket_number TEXT        NOT NULL UNIQUE,
  email         TEXT        NOT NULL,
  name          TEXT,
  platform      TEXT,
  tier          TEXT,
  issue         TEXT        NOT NULL,
  status        TEXT        NOT NULL DEFAULT 'open',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS support_tickets_email_idx      ON support_tickets (email);
CREATE INDEX IF NOT EXISTS support_tickets_status_idx     ON support_tickets (status);
CREATE INDEX IF NOT EXISTS support_tickets_created_at_idx ON support_tickets (created_at DESC);

-- Optional: view all open tickets ordered by newest first
-- SELECT * FROM support_tickets WHERE status = 'open' ORDER BY created_at DESC;
