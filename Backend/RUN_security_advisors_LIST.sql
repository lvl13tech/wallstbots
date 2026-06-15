-- ============================================================================
-- READ-ONLY: list the remaining security issues so we can see them exactly.
-- Changes nothing. Run in Supabase SQL Editor and paste the results back.
-- ============================================================================

-- 1) Tables in 'public' schema that DON'T have RLS enabled (the classic finding)
SELECT n.nspname AS schema, c.relname AS object, c.relkind AS kind,
       c.relrowsecurity AS rls_enabled
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relkind = 'r'                 -- ordinary tables
  AND c.relrowsecurity = false
ORDER BY c.relname;
-- Any rows here = public tables still without RLS.

-- 2) Tables that HAVE policies but RLS disabled (policies silently doing nothing)
SELECT DISTINCT p.tablename
FROM pg_policies p
JOIN pg_class c ON c.relname = p.tablename
WHERE c.relrowsecurity = false
ORDER BY p.tablename;

-- 3) All VIEWS in public, and whether they run as SECURITY DEFINER (the risk)
--    'definer' / 'not set' = flagged; 'invoker' = safe.
SELECT c.relname AS view_name,
       COALESCE(
         (SELECT option_value FROM pg_options_to_table(c.reloptions)
          WHERE option_name = 'security_invoker'), 'not set => DEFINER'
       ) AS security_invoker
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'v'
ORDER BY c.relname;

-- 4) Functions in public with mutable search_path (a common advisor warning)
SELECT p.proname AS function_name,
       CASE WHEN p.prosecdef THEN 'SECURITY DEFINER' ELSE 'invoker' END AS security,
       COALESCE(array_to_string(p.proconfig, ', '), '(no search_path set)') AS config
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
ORDER BY p.proname;
-- Functions showing '(no search_path set)' are the "Function Search Path Mutable" warnings.
