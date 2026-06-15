-- ============================================================================
-- SECURITY FIX — close the 3 Supabase advisor issues (RLS + view)
-- ============================================================================
-- WHY THIS IS SAFE:
--   The FastAPI backend connects over a DIRECT Postgres connection using the
--   service-role/owner credentials, which BYPASSES row-level security. So
--   enabling RLS and switching the view to security_invoker does NOT affect
--   any backend functionality. RLS only governs access via the PUBLIC anon /
--   authenticated API keys (the keys shipped in browser JS). This closes the
--   hole where a browser key could read other users' data.
--
-- Idempotent / re-runnable. Run RUN_FIRST_security_TEST.sql before & after.
-- ============================================================================

-- ── 1. portfolio_comments: policies already exist, just turn RLS ON ──────────
ALTER TABLE portfolio_comments ENABLE ROW LEVEL SECURITY;
-- (Existing policies: public reads non-deleted; users insert/update only their
--  own. They start enforcing the moment RLS is on.)

-- ── 2. support_tickets: enable RLS with NO public policies ───────────────────
-- Only the backend (service role, which bypasses RLS) and admins should ever
-- read/write tickets. With RLS on and no anon/authenticated policy, the public
-- keys get NOTHING — which is exactly what we want for private support data.
ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;

-- Belt-and-suspenders: also revoke direct table grants from the public roles,
-- so even setup quirks can't expose it via the API.
REVOKE ALL ON support_tickets FROM anon;
REVOKE ALL ON support_tickets FROM authenticated;

-- ── 3. user_dashboard_summary view: run as INVOKER, not DEFINER ──────────────
-- SECURITY DEFINER made the view run with the owner's rights (bypassing RLS for
-- whoever queried it). security_invoker = true makes it respect the caller's
-- permissions instead. Backend (service role) is unaffected.
ALTER VIEW user_dashboard_summary SET (security_invoker = true);

-- Optional hardening: this view exposes every user's email/spend/referral data,
-- so the public browser role should not be able to read it at all. The backend
-- reads it over the service connection, so this does not break the dashboard.
REVOKE ALL ON user_dashboard_summary FROM anon;
REVOKE ALL ON user_dashboard_summary FROM authenticated;

-- Done. Re-run RUN_FIRST_security_TEST.sql: RLS should be true on both tables,
-- the view's security_invoker should be 'true', and anon grants should be gone.
