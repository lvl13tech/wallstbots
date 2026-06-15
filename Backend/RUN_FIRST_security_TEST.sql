-- ============================================================================
-- READ-ONLY security inspection — run FIRST in Supabase SQL Editor.
-- Changes NOTHING. Shows the current state of the 3 advisor issues so you can
-- see exactly what the FIX will change.
-- ============================================================================

-- 1) Is RLS enabled on the two public tables? (relrowsecurity = true means ON)
SELECT relname AS table_name, relrowsecurity AS rls_enabled
FROM pg_class
WHERE relname IN ('support_tickets', 'portfolio_comments');
-- Expect (problem state): rls_enabled = false for one or both.

-- 2) What policies already exist on those tables?
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE tablename IN ('support_tickets', 'portfolio_comments')
ORDER BY tablename, policyname;
-- portfolio_comments should list 3 policies; support_tickets likely none.

-- 3) Does the dashboard view run as SECURITY DEFINER (the flagged risk)?
SELECT c.relname AS view_name,
       COALESCE(
         (SELECT option_value FROM pg_options_to_table(c.reloptions)
          WHERE option_name = 'security_invoker'),
         'not set (defaults to DEFINER)'
       ) AS security_invoker_setting
FROM pg_class c
WHERE c.relname = 'user_dashboard_summary';
-- 'not set ...' or 'false' = runs as DEFINER (the problem). 'true' = fixed.

-- 4) Which roles can read these objects directly (anon = public browser key)?
SELECT table_name, grantee, privilege_type
FROM information_schema.role_table_grants
WHERE table_name IN ('support_tickets', 'portfolio_comments', 'user_dashboard_summary')
  AND grantee IN ('anon', 'authenticated')
ORDER BY table_name, grantee, privilege_type;
-- Shows whether the public 'anon' role can currently read these.
