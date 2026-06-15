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

- **2026-06-15 (later)** — Corrected the whole doc set to the real platform model: 3 product sites (wallstbots/aistocks/bitbot13) + lvl13 parent landing page (read-only, hands-off, Rule 10). Recorded migration history (aistocks was originally lvl13), Stripe-as-active-checkout (PayPal legacy), and lvl13's exact backend surface. Verified live lvl13 and backed it up. Wrote `HANDOFF_2026-06-15.md`. Archived dated historical docs to `_archive/`. No product-site code changed yet. Next: run the regression checklist to populate the per-site status table.
- **2026-06-15** — Created control documents (ARCHITECTURE, PROJECT_STATUS, SESSION_START, CLAUDE.md, REGRESSION_CHECKLIST) after the platform reached a fully-broken state from clone drift. No code changed yet.
