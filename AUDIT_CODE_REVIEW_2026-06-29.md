# Code Audit — Security, Performance, Best Practices (2026-06-29)

Pre-reset full-codebase review: Backend/main.py (4,188 lines), 3 refresh engines +
shared bot13_engine.py + refresh_portfolios.py + send_emails.py, 3 product frontends.
**Overall: healthy and launch-ready. No critical vulnerabilities. A short list of
hardening + scaling items below, none blocking the reset.**

---

## SECURITY — strong

PASS:
- **SQL injection: none.** All 8 f-string queries interpolate only hardcoded SQL
  fragments / literal table+column names; every user value goes through %s params.
- **No hardcoded secrets.** JWT_SECRET, STRIPE_SECRET_KEY, TURNSTILE_SECRET_KEY,
  INTERNAL_API_KEY, DB creds all from os.getenv / secrets.json.
- **secrets.json** is gitignored AND not tracked by git.
- **CORS** locked to the 4 product domains + www + localhost — not a wildcard.
- **All 6 /internal/* endpoints** require the internal key (verify_internal_key).
- **JWT** verified properly (HS256 Supabase secret + ES256 via JWKS). Auth + password
  hashing delegated to Supabase (not rolled by hand).
- **17 unauthenticated endpoints** are all legitimately public (auth, public tracker
  data, leaderboard, public portfolio views, Stripe webhook, health, support ticket,
  promo/referral validation). Nothing sensitive exposed.
- Signup now gated by Turnstile captcha (closed the spam-bot hole).

FINDINGS (low/medium — recommend, not blocking):
1. **No rate limiting** on abuse-prone public endpoints: /auth/login,
   /auth/password-reset, /support/ticket, /promo-codes/validate. Captcha covers signup
   but not these. RECOMMEND: add slowapi (IP-based limits) or Cloudflare rate rules in
   front of these paths. (Cloudflare WAF rate-limiting is the quickest win — no code.)
2. **Error leakage:** 6 spots raise `HTTPException(..., detail=str(e))`, returning raw
   internal error text (DB messages, etc.) to the client. RECOMMEND: log the real error
   server-side, return a generic "Internal error" to the client. (lines ~463, 1541,
   1826, 1877, 1986, 3223.)

---

## PERFORMANCE — good foundation

PASS:
- **DB connection POOL** (psycopg_pool ConnectionPool), not a new connect per request —
  the single most important backend perf choice, already done right.
- Frontend page weight reasonable: Chart.js 204KB (CDN-cacheable, loaded once),
  app.js ~90-100KB, dashboard ~110KB. No render-blocking surprises.
- No leftover console.log in production frontend JS.

FINDINGS:
3. **N+1 in /admin/email-subscribers** (the send_emails source): the `for u in users`
   loop runs ~3 queries PER user (tier check + holdings + bot13 activity). Fine at 2
   members; at hundreds it's hundreds of round-trips per email run. RECOMMEND: replace
   with 3 set-based queries (one holdings query for all users, one activity query,
   joined in Python) before the member base grows. Not urgent at current scale.
4. **app.js / dashboard.html are unminified** (~90-116KB raw each). Minifying would cut
   ~40-50% off transfer. Minor; Cloudflare can auto-minify (Speed > Optimization) with
   zero code change. RECOMMEND: enable Cloudflare auto-minify rather than a build step.
5. Public pages fetch with cache:'no-store' (10 per site) — correct for live trading
   data, but confirm static assets (app.js, chart.js) get long cache headers from
   Cloudflare so only the data calls hit origin.

---

## BEST PRACTICES — clean, a few notes

PASS:
- No bare `except:` in production engines/backend (only one in audit_integrity.py, a
  read-only tool — harmless). Broad `except Exception` used defensively, acceptable.
- No .env/.pem/.key/credential files tracked in git.
- Parity discipline holding across the 3 product engines (verified this session).

FINDINGS:
6. **aistocks committed state.json is frozen at Jun 13** (16 days stale). NOT a bug:
   the aistocks workflow runs the engine on a fresh checkout, overwrites state.json
   locally from live prices, pushes to the BACKEND, and only commits a heartbeat — the
   site reads the backend (current), not the stale committed file. **Reset implication:
   aistocks reset MUST target the backend (/internal/tracker/push) + member DB, not the
   disk file** (the engine ignores/overwrites disk on aistocks). wallstbots + bitbot13
   DO commit their data, so they need disk + backend + DB. full_reset_all.py handles
   this per-platform difference.
7. Unused import: `stamp_and_log` in refresh_portfolios.py (member log now derives from
   the tracker log). Harmless; remove on next touch.
8. Many one-off reset/fix scripts in Project/scripts/ (reset_lvl13, reset_state_json,
   fix_bitbot13_source, etc.) — historical clutter. RECOMMEND: archive into a
   scripts/_archive/ folder so the active engine scripts are easy to find.

---

## VERDICT
No blocker for the final reset. Recommended quick wins (all no-code or low-risk):
Cloudflare rate-limiting + auto-minify (dashboard toggles), and swap the 6 `detail=str(e)`
for generic messages. The N+1 and script cleanup are scale/maintenance items for later.
