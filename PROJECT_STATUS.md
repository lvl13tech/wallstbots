# PROJECT_STATUS.md — What Works and What's Broken

**Keep this file honest and current.** Update it at the end of every work session.
When Claude finishes a change, the LAST step is to update this file.

Last updated: 2026-06-15 · Status: **BROKEN — no site is fully functional**

---

## Overall State (plain English)

The Wall St Bots **product** is three near-identical sites: **wallstbots.tech** (sector
stocks), **aistocks.tech** (AI/quantum stocks), **bitbot13.tech** (crypto + crypto hours). It
was built by getting **one** site working, then **cloning** it. Each clone was edited
separately and features were added on top. Because the "shared" files are actually three
separate copies (see `ARCHITECTURE.md` §6), the sites drifted apart — fixes to one copy don't
reach the others, so right now **none** of the three product sites is fully working end-to-end.

**lvl13.tech is the parent-company landing page, NOT a product site.** It is excluded from
this status table and from all stabilization/parity work. 🔒 Do not modify it (CLAUDE.md
Rule 10). Its only backend dependency is a read-only cross-site Bot13 P&L box.

The goal right now is **not** new features. Get back to **one** fully working product site
(wallstbots), lock it as the reference, then bring the other two to parity — ideally
de-duplicating into shared code so this can't happen again.

---

## Per-Site Status (the 3 product sites)

Mark each row honestly. Use: ✅ works · ⚠️ partly works · ❌ broken · ❔ untested

| Capability | wallstbots | aistocks | bitbot13 |
|------------|:----------:|:--------:|:--------:|
| Homepage loads | ❔ | ❔ | ❔ |
| Live leaderboard shows data | ❔ | ❔ | ❔ |
| Signals section | ❔ | ❔ | ❔ |
| News (correct topic only) | ❔ | ❔ | ❔ |
| The Race / fund pages | ❔ | ❔ | ❔ |
| Reports | ❔ | ❔ | ❔ |
| Signup | ❔ | ❔ | ❔ |
| Login | ❔ | ❔ | ❔ |
| Logged-in dashboard | ❔ | ❔ | ❔ |
| Get Yours / pricing | ❔ | ❔ | ❔ |
| Stripe checkout | ❔ | ❔ | ❔ |
| Stripe billing portal (Manage/Cancel) | ❔ | ❔ | ❔ |
| Referral dashboard | ❔ | ❔ | ❔ |
| Admin panel | ❔ | ❔ | ❔ |
| Chatbot (quick replies + typed input) | ❔ | ❔ | ❔ |

> Checkout is **Stripe** (`/stripe/create-checkout` + webhooks). PayPal config still exists in
> `main.py` but is legacy, not the active flow.

**Separate, read-only check for lvl13 (do not edit lvl13):**

| Capability | lvl13 (parent) |
|------------|:--------------:|
| Landing page loads | ❔ |
| Bot13 P&L box reads all 3 product sites | ❔ |
| Contact form posts | ❔ |

> **First task for the next session:** stop fixing, and fill these tables in by running
> `REGRESSION_CHECKLIST.md` against the three product sites (and the small read-only lvl13
> check). You cannot fix drift you can't see. **wallstbots.tech is the most up-to-date and is
> the reference.**

---

## 🔒 Pre-launch security (Supabase advisors)

✅ **The 3 CRITICAL issues FIXED & verified 2026-06-15** (ran in Supabase SQL Editor):

- `portfolio_comments` — RLS now ENABLED (verified `relrowsecurity = true`); public anon
  INSERT/UPDATE/DELETE/TRUNCATE revoked. Public SELECT kept (comments are meant to be readable)
  but now filtered to non-deleted rows by the existing policy.
- `support_tickets` — RLS ENABLED (verified `true`); all anon + authenticated grants revoked →
  backend (service role) only.
- `user_dashboard_summary` view — set `security_invoker = true`; anon + authenticated read revoked.

**Why safe:** the FastAPI backend uses a direct Postgres (service-role) connection that bypasses
RLS, so backend features are unaffected. Confirmed working. Fix files retained:
`Backend/RUN_FIRST_security_TEST.sql`, `Backend/security_FIX_rls.sql`.

✅ **The remaining advisor issues FIXED & verified 2026-06-15** (all 7 now resolved):

- Functions `generate_referral_code` and `update_timestamp` — pinned `SET search_path = public`
  (cleared the "Function Search Path Mutable" warnings). Verified both show `search_path=public`.
- Views `bot_latest_performance`, `promo_code_usage`, `user_referral_stats` — set
  `security_invoker = true` (same fix as `user_dashboard_summary`). `promo_code_usage` and
  `user_referral_stats` also had anon/authenticated read revoked (sensitive). `bot_latest_performance`
  left publicly readable on purpose (shown on the product sites).

**Final verification query returned 0 rows** — no public tables without RLS, no SECURITY DEFINER
views remaining. Full security advisor list cleared. (Re-check the Supabase Advisor page to see
the count at 0.)

---

## Live audit 2026-06-15 (public pages, all 3 product sites)

Audited the rendered live sites (not just code). Most of the old known-bugs list is STALE —
already fixed in current code:
- ✅ Chatbot: now a proper `<form id="chatbotForm">` with `chatbotRenderQuick()` wired up in all
  3 sites; the old undefined `handleChatbotInput` is gone. Not broken.
- ✅ `#/login` and `#/signup`: route to real standalone pages (e.g. `/login`), not the homepage.
- ✅ The Race / Signals / News / Reports / Get-Yours: render cleanly on all 3 (correct per-site
  numbers — wallstbots $55k/55, aistocks $50k/50, bitbot13 $50k/50 coins), no error banners, no NaN.
- ✅ aistocks shows TODAY's data on the rendered site (data-pipeline fix verified end-to-end).

**Real bug found + FIXED:** Signals "last run -226m ago" showed NEGATIVE minutes. Cause:
`relTime()` did `new Date(iso)` on a timezone-less UTC timestamp (e.g. "2026-06-15T20:32:15"),
which JS parses as LOCAL time → looks hours in the future. Fixed in all 3 `app.js`: append "Z"
when no tz suffix, and clamp negative to 0. (Also noted clone drift: `relTime` sat at different
line numbers across the 3 files — bodies were identical, fix applied to all.)

**Real bug found + FIXED — FREE signup was 404 (missing backend feature).** The FREE
"Get Free Signals" box called `POST /subscriptions/free-signup`, which never existed on the
backend (404 → "Something went wrong"). The free tier was simply never built (the DB already
defaults `subscription_tier='free'`). Fix: added `POST /auth/signup-free` to `main.py`
(mirrors `signup-with-admin-code`: creates a real Supabase auth user + users row at
`subscription_tier='free'`, returns a JWT, logs them in). A free account is a NORMAL account —
when they upgrade, the existing Stripe webhook flips the same row's tier; no second signup.
Frontends (all 3): the FREE box now collects email + password and calls `/auth/signup-free`,
dropping the user into their dashboard. **Needs backend redeploy to Cloud Run** (frontends
auto-deploy via Cloudflare on push).

**aistocks BOT13 end-of-day display blanked (migration side-effect, NOT a code bug) —
WATCH TOMORROW.** After close on 2026-06-15, aistocks BOT13 showed empty HOLD (positions=0,
picks=[], projected_return=0, day_pct=0) while wallstbots correctly PRESERVED its completed
trade (decision=TRADE, 5 positions, "session complete" log, day +11.5%). Investigated: the
market-closed branch in refresh_*.py preserves the day's trade ONLY if
`prev_b13_strategy.decision == "TRADE"`. The code is **byte-identical** between
refresh_wallstbots.py and refresh_lvl13.py — so it's a DATA-state difference, not logic.
Cause: today's `lvl13→aistocks` platform-key switch (+ move to API-fallback state loading)
interrupted the aistocks bucket's prior-TRADE chain, so the preserve-branch had nothing to
preserve and wiped to empty. wallstbots' chain was never disrupted. **Self-heals** once
aistocks runs a clean open-session TRADE tomorrow (it'll then store decision=TRADE and the
after-hours refresh will preserve it). ⏳ VERIFY 2026-06-16 after the open-session refresh:
aistocks BOT13 should look like wallstbots at end of day.

✅ **HARDENED 2026-06-15 (so this can never blank again).** Added a graceful fallback to the
market-closed branch in ALL 3 refresh scripts (parity): if the prior strategy chain isn't
"TRADE" but there ARE positions stored from today, preserve and re-price those (shown as a
held TRADE session) instead of wiping to empty. Positions are re-enriched with live prices
below, so they display current values. Now the end-of-day page only goes empty when there
genuinely are no positions. Needs no backend deploy (these are the GitHub-Actions refresh
scripts) — just pushed to the repo so the next cron run uses them.

**Dashboard design restored (2026-06-15).** Owner reported the members dashboard DESIGN
changed (not a code bug). Diffed wallstbots `dashboard.html` against the last June-11 version
(commit 73acf9d): the post-11 changes were mostly good (lvl13→aistocks rebrand, upgraded
referral "Invite & Earn" panel, openStripePortal fix) — KEPT those. The actual unwanted change
was **two ADDED sections: "Live Bot Session" and "Market News."** Removed both sections + their
`loadNews()`/`loadBotSession()` bootstrap calls on **all 3 dashboards** (parity). Also fixed a
wallstbots-only bug introduced after June 11: a stray duplicated/unclosed DB-latency `<div>` in
the webmaster stats panel. Done surgically on the current files (design back, good code kept) —
not a wholesale revert.

**bot-detail.html was TRUNCATED on all 3 sites — FIXED 2026-06-15.** Owner reported the
portfolio/bot-detail page stuck on "Loading…" everywhere with an EMPTY console (no JS error).
Cause: the file was cut off mid-line in the window-bindings block (`window.clo…`), so it had
no `</script>`, no closing tags, and — critically — the `document.addEventListener('DOMContentLoaded', init)`
bootstrap was missing → `init()` never ran → every section frozen. (Line counts proved it: the
last COMPLETE version was `c5ecab8` June 11 at 1416 lines; it dropped to 1386 truncated at
`dcb73fb` June 12 and stayed broken since.) Fix: restored the exact missing tail (full window
bindings + DOMContentLoaded→init + `</script></body></html>`) from the c5ecab8 version onto each
current file, preserving all newer body content (bot_fund_state reads etc.). Applied to all 3
sites (parity); verified each now has exactly one clean ending. **This is the same class of bug
as commit `ecf5f61` ("repair truncated app.js — unexpected end of input") — truncation has hit
this project repeatedly; worth a guard.** Needs deploy (Cloudflare auto on push).

**portfolio-fund.html ALSO truncated — FIXED 2026-06-15.** After bot-detail loaded, its in-page
links (fund cards → portfolio-fund.html) "didn't load" because portfolio-fund.html was truncated
the same way (cut at line 1008 mid nav-toggle comment; missing DOMContentLoaded→init bootstrap +
window bindings + closing tags). Truncation came from `c1f7daa` (June 13, the same mega-commit).
Last complete version: `c5ecab8` (June 11, 1039 lines); current was 1008. Restored the 31-line
tail onto all 3 sites (parity), preserving newer body content (d9859b8 bot_fund_state stat-card
change). **Full truncation sweep done:** scanned every member HTML across all 3 sites — only
bot-detail, dashboard (design, not truncation), and portfolio-fund were affected; index/admin/
login/leaderboard all end cleanly. **ROOT-CAUSE INVESTIGATED + GUARD ADDED (2026-06-15).** Findings: (1) NO script in the repo
rewrites these HTML files — the JSON deploy script (`deploy_to_hostgator.py`) uses binary mode
and only touches *.json; `update-frontend-api-urls.py` correctly uses encoding='utf-8' and only
touches login/signup/index. So the truncation is NOT a deploy-script bug. (2) Every truncation
cut off at a box-drawing char (`─` in the `// ── … ──` comments) leaving a `�` replacement char.
That signature = a tool/editor that re-wrote the whole file with the wrong encoding or hit an
output-length limit mid-file (consistent with an AI/editor regenerating large files; the repo
also lives under OneDrive, which can interrupt writes). Exact tool unconfirmed (owner unsure how
files are edited). **GUARD (makes cause irrelevant for prevention):** added a git pre-commit hook
`Project/scripts/pre-commit-truncation-guard.sh` that BLOCKS any commit containing an HTML file
not ending in `</html>`, installed via `INSTALL-truncation-guard-doubleclick-me.bat` (run once),
plus a standalone `CHECK-truncation-doubleclick-me.bat` to scan on demand. A truncated file can no
longer reach git/production. **Optional next:** replace the `─` box-drawing chars in comments with
plain ASCII so the specific bytes tools choke on are gone (belt-and-suspenders).

**Guard already caught one (2026-06-15):** the new checker flagged `aistocks.tech/signup.html`
as truncated (cut mid-function at line 245). It's orphaned dead code — nothing links to it
(/signup redirects to login.html#signup; real signups go via Get Yours / free-signup), and it
exists on no other site. Deleted via `FINALIZE-guard-and-cleanup-doubleclick-me.bat`. 21/22 HTML
files were clean. **Guard layers:** `SAFE-DEPLOY-doubleclick-me.bat` (runs PowerShell check before
every deploy — THE reliable layer), git pre-commit hook (installed; fires if Git-for-Windows runs
.sh hooks), `CHECK-truncation-doubleclick-me.bat` (on-demand). Checkers use PowerShell (plain
batch choked on HTML special chars — first version gave false positives, now fixed).

**Not yet tested (needs a test login):** admin panel, signup→Stripe checkout, referral dashboard,
logged-in member portfolio data. Owner to verify dashboard + bot-detail + portfolio-fund after deploy.

---

## Known Bugs (from SITE_SPEC.md audit, 2026-05-20 — verify if still present)

### bitbot13.tech/assets/app.js
- `handleChatbotInput()` is called but never defined → chatbot text input crashes silently
- `chatbotRenderQuick()` is defined but never invoked → quick-reply buttons stay empty
- `#/login` and `#/signup` hash routes unhandled → "Log in" links fall through to homepage
- `admin.html` getToken reads only `auth_token`, missing the `bitbot13_jwt` fallback

### aistocks.tech (the migrated former lvl13 trading site)
- Its refresh script is `refresh_lvl13.py` (NOT renamed — owner confirmed this is fine). It carries the AI/quantum universe and pushes `{"platform":"lvl13"}`.
- It is **missing** the `state.json` try/except + live-API fallback (confirmed — see Backend section).
- Check `admin.html` JWT fallback chain on aistocks (VERIFY against the deployed site).

### lvl13.tech (parent site — NOT a product; do not "fix" as part of this work)
- The repo's `Frontends/lvl13.tech/` still holds stale pre-migration trading-clone files. This
  is known and tracked separately (optional `CLEANUP-lvl13-leftovers-*.bat`); it is NOT a
  product-site bug and must not be folded into stabilization work. The live lvl13 landing page
  is correct and backed up at `Backups/lvl13.tech_live_2026-06-15_1419/`.

### Backend / refresh scripts
- ✅ **FIXED 2026-06-15 — state.json corruption guard now on all 3 refreshers.** Ported
  bitbot13's try/except + live-API fallback into `refresh_wallstbots.py` and `refresh_lvl13.py`
  (all three now identical except platform string + starting-capital default). Also fixed the
  `[wallstbots]` → `[lvl13]` mislabel in `refresh_lvl13.py`. ✅ Syntax-verified 2026-06-15:
  all three compile cleanly (Python 3.14.4, via CHECK-refresh-scripts .bat).
- ✅ **FIXED 2026-06-15 — `origin_platform` DB constraint corrected.** Ran the corrective
  ALTER in Supabase; constraint now `CHECK (origin_platform IN ('aistocks','bitbot13','wallstbots','unknown'))`
  (was the stale `lvl13/bitbot13/wallstbots`). Verified via `pg_get_constraintdef`. `subscriptions`
  table was empty (0 rows) so no data relabel was needed. Backend was already correct (Stripe
  webhook writes the right platform values) — no code change required.
- **AI site refresh runs under the `lvl13` name (intentional — owner confirmed OK).** `refresh_lvl13.py` feeds the AI/quantum site (now aistocks.tech) and pushes `{"platform":"lvl13"}`. Not to be renamed.
- News scripts historically pulled broadly without strict source/keyword filters → off-topic articles slip through (verify per site).

---

## The Root Cause (do not lose sight of this)

**Cloning instead of sharing.** Three copies (one per product site) of `auth.js`, `api.js`, `app.js`, `login.html`, `dashboard.html`, `admin.html`, `bot-detail.html`, and the `refresh_*.py` scripts. Every fix has to be made three times or the sites drift. This is the thing to fix structurally — see the recovery plan below. (lvl13 is not part of this set.)

---

## Recovery Plan (the order to do things in)

1. **See the truth.** Run `REGRESSION_CHECKLIST.md` on the three product sites; fill in the table above. (Run the small lvl13 check read-only.)
2. **Pick the reference.** wallstbots.tech is currently the most complete. Confirm it is the cleanest, then declare it the reference.
3. **Get ONE site fully green.** Bring the reference site to 100% on its own checklist. Do not touch the other two yet.
4. **Lock it.** Commit. Tag it. This is the known-good baseline you can always return to.
5. **Bring the other two to parity — one at a time** (aistocks, then bitbot13). Port the reference's logic, verifying the checklist after each. Never two at once. Respect bitbot13's allowed differences (crypto class + crypto hours).
6. **De-duplicate (the real fix).** Once all three match, refactor the duplicated files into a single shared source each site imports, plus one parameterized refresh engine. After this, a fix is made once and is correct everywhere.

> Steps 1–5 stabilize. Step 6 is what stops this from ever happening again. Per the platform-health priority, step 6 is not optional — it's the point.

---

## Session Log (append newest at top)

- **2026-06-15 (aistocks data pipeline FIXED)** — Found aistocks.tech was showing STALE
  data (June 12) because `refresh_lvl13.py` pushed to the backend as platform `lvl13` while
  the site reads platform `aistocks` — separate buckets, no backend alias (verified live: the
  aistocks bucket's last_refresh was 2026-06-12). Fixed: changed all 4 platform refs in
  `refresh_lvl13.py` (`push_to_api`, snapshot trigger, fallback read, `refresh_portfolios.run`)
  from `lvl13` → `aistocks`. Also cleaned the `refresh-lvl13.yml` workflow: removed the
  vestigial git-commit-to-`Frontends/lvl13.tech/data/` step (the cause of the earlier merge
  conflict; sites read the API, not committed JSON), added `mkdir -p` so the local data dir
  exists for `send_emails.py`, made the verify step tolerant, and corrected the misleading
  name/comments. ✅ **VERIFIED LIVE 2026-06-15:** ran the workflow manually (green); logs
  showed `[push:state] OK` + `[portfolios] running simulations for platform=aistocks`; backend
  `aistocks` bucket now reads `last_refresh: 2026-06-15T20:32` with a fresh 06-15 snapshot (was
  stuck on 06-12). The earlier "still 06-12" read was a stale CDN cache, not a failure.
  NOTE: wallstbots/bitbot13 workflows still have
  the (harmless) commit-to-data step — their data folders still exist in the repo, so it's not
  broken; optional future cleanup to drop it from all three for consistency.
- **2026-06-15 (committed & pushed)** — All session work committed and pushed to
  origin/master (`b0b794d`): doc corrections, refresh state.json crash-guard, origin_platform
  constraint fix, Supabase security advisor fixes (all 7 cleared), repo junk cleanup +
  .gitignore, and removal of the stale `Frontends/lvl13.tech/` trading-clone files. Merged 4
  automated cron data-refresh commits cleanly. **⚠️ OPEN ITEM:** a scheduled job still runs
  `lvl13 data refresh` writing to the now-removed `Frontends/lvl13.tech/data/` path (it caused
  a merge conflict and re-creates files nobody reads). Retire or repoint that GitHub Actions
  job next.
- **2026-06-15 (later)** — Corrected the whole doc set to the real platform model: 3 product sites (wallstbots/aistocks/bitbot13) + lvl13 parent landing page (read-only, hands-off, Rule 10). Recorded migration history (aistocks was originally lvl13), Stripe-as-active-checkout (PayPal legacy), and lvl13's exact backend surface. Verified live lvl13 and backed it up. Wrote `HANDOFF_2026-06-15.md`. Archived dated historical docs to `_archive/`. No product-site code changed yet. Next: run the regression checklist to populate the per-site status table.
- **2026-06-15** — Created control documents (ARCHITECTURE, PROJECT_STATUS, SESSION_START, CLAUDE.md, REGRESSION_CHECKLIST) after the platform reached a fully-broken state from clone drift. No code changed yet.
