# CLAUDE.md — Rules for Working in This Repository

This file is automatically loaded by Claude when working in this folder. These rules
exist because this project keeps breaking when one fix breaks something that already
worked. Follow them exactly. They override the urge to be fast or clever.

---

## Context (so you don't have to rediscover it)

This is the Level 13 trading-simulation platform. There are **four domains in two tiers**:

- **Product (3 near-identical sites):** `wallstbots.tech` (sector stocks), `aistocks.tech`
  (AI/quantum stocks), `bitbot13.tech` (crypto). These run the trading simulation. They are
  identical clones except for their asset universe, and bitbot13 additionally differs by
  asset class (crypto) and trading hours (crypto sessions, not equity market hours).
- **Parent (1 site):** `lvl13.tech` (JBM Capital LLC) owns the Wall St Bots platform. It is
  **strictly a corporate/marketing landing page** — no login, no pricing, no Stripe, no
  signup, no simulation. Its ONLY backend use is: 3× `GET /public/tracker/state?platform=
  {wallstbots,aistocks,bitbot13}` (feeding the **BOT13 P&L text box**) + `POST /contact`.
  **🔒 NEVER modify lvl13.tech unless the owner explicitly says so — see Rule 10.** (Heads-up:
  the repo's `Frontends/lvl13.tech/app.js` is the old pre-migration trading clone and does
  NOT match the live site — do not redeploy from it. See ARCHITECTURE.md §0.)

All four share **one** FastAPI backend and **one** Supabase database. Python `refresh_*.py`
scripts simulate five trading bots and push results to the backend; the product sites only
read that data. **Note:** `aistocks.tech` was originally `lvl13.tech` — the AI/quantum
trading site was migrated to the aistocks domain, then lvl13.tech was rebuilt as the parent
company. The authoritative platform whitelist is `("aistocks", "bitbot13", "wallstbots")` in
`Backend/main.py`; lvl13 is intentionally not in it.

**Read `ARCHITECTURE.md` and `PROJECT_STATUS.md` before making changes.**

The owner vibe-codes and does not read code line by line. Your explanations must be in
plain English. The owner has a networking background, not a software-engineering one.

---

## The Root Problem You Must Not Make Worse

The product sites were **cloned**, so `auth.js`, `api.js`, `assets/app.js`, `login.html`,
`dashboard.html`, `admin.html`, and the `refresh_*.py` scripts exist as **separate copies
per product site** (wallstbots, aistocks, bitbot13). Editing one copy does not change the
others. This drift is why "fixing one site breaks another." **wallstbots.tech is the
reference site.** (lvl13.tech, the parent site, is outside this parity set — see Rule 3.)

---

## Rule 0 — Data Integrity Is the Mission (overrides everything)

**Data integrity is this platform's mission statement.** Every number shown must be REAL and
VERIFIABLE from real trades. Nothing fictitious, ever — no matter how convenient.

**The Day-1 Rule (every fund AND every member portfolio, all 5 bots + baselines):**

- A fund is **reset** / a portfolio is **created** on day 0. There is no "before."
- Starting capital = **(number of assets) × $1,000**. Nothing else.
- **Nothing trades on the creation/reset day.** The fund/portfolio holds starting capital flat
  that day and takes its **first real entries at the NEXT trading session** (crypto = next day;
  equity = next weekday, skipping weekends + US market holidays). This keeps every entry clean at
  a real session open — no partial-day numbers to reconcile. Show users a clear "trading begins
  <next session>" message until then. (`next_trading_day()` in `bot13_engine.py` computes the date.)
- **Never** inherit prior data, **never** scale from the platform's since-launch performance, and
  **never** reference "yesterday / last session" for something that started today.
- Every trade must be verifiable from its real entry price.

This is a simple concept. Do not "make it up" or make it more complicated. Members will constantly
create portfolios — day 1 is the common case. A new portfolio starts at its own capital and tracks
forward from its own real entries; a reset restarts a fund the same way. If code violates this, the
code is wrong. (Historical bug: member value was scaled by `platform_total / platform_sc`, so a
portfolio created on day 30 inherited 30 days of platform gains — forbidden by this rule.)

---

## Rule 1 — Smallest Possible Change

Make the smallest change that achieves the goal. Do not refactor, rename, reformat, or
"clean up" unrelated code in the same edit. If you see something else worth fixing, list
it separately and let the owner decide. One concern per change.

## Rule 2 — Test Before You Fix (the vibe-coder regression test)

Before you change anything:
1. State what currently works that your change could affect.
2. Point to the relevant section of `REGRESSION_CHECKLIST.md` (or add one).
3. Get agreement on what "still working" means.
Only then apply the fix. After the fix, re-run the relevant checklist items.

Do **not** apply a fix and a feature in the same step. Stabilize first.

## Rule 3 — The Parity Rule (most important)

These files are duplicated across the **three product sites** (wallstbots, aistocks,
bitbot13) and MUST stay functionally identical (only branding strings, the per-site JWT key,
and — for bitbot13 — the crypto asset class and trading hours may differ). **lvl13.tech is
the parent site and is NOT part of this parity set; do not sync product-site changes into it
unless they touch the shared backend contract or the cross-site rollup it reads.**

- `auth.js`
- `api.js`
- `assets/app.js`
- `login.html`, `dashboard.html`, `admin.html`
- `refresh_*.py` (the simulation engines)

**If you change one copy, you change every copy in the same change** — or you explicitly
tell the owner "I only changed wallstbots; the other two product sites still have the old version"
and explain why. Never leave silent drift. When unsure, copy from the reference site
(wallstbots.tech) rather than inventing a new version.

## Rule 4 — Frontends Don't Decide Anything

No prices, discounts, promo logic, trading math, or business rules in any `.html` or
frontend `.js` file. That logic lives in `Backend/main.py`. Frontends only render what
the backend returns. If a task seems to need logic in the frontend, push it to the
backend instead and explain why.

## Rule 5 — Respect the Data Contract

The shape of the data `refresh_*.py` pushes must match what `app.js` reads
(`funds`, `snapshots`, `leaderboards`, `value.total`, `value.pnl_pct`, `positions[]`,
etc.). If you rename or restructure a field on one side, update every consumer in the
same change and call it out. See `ARCHITECTURE.md` §8.

## Rule 6 — Explain Everything in Plain English

For every change, end with a short, non-technical summary:
- **What I changed:** (one or two sentences)
- **Why:** (the problem it solves)
- **What it could affect:** (other sites, the dashboard, the bots…)
- **How you verify it:** (exact clicks/steps the owner can do)

## Rule 7 — Long-Term Health Over Quick Fixes

Never take the quickest hack. Do what is best for the long-term health of the platform
and its paying members, even if slower. If the right fix is bigger than the quick one,
say so and recommend the right one.

## Rule 8 — Deliverables the Owner Can Run

When the owner needs to execute something, provide a `.bat` file (Windows) or exact
copy-paste, step-by-step instructions. Never assume command-line fluency.

## Rule 9 — End-of-Session Hygiene

Before ending a session that changed anything:
1. Update `PROJECT_STATUS.md` (the per-site table and the session log).
2. State what is now known-good vs still untested.
3. Remind the owner of the git commit/push step (or provide the `.bat`).

## Rule 10 — Hands Off lvl13.tech

**Never make any change to lvl13.tech unless the owner explicitly tells you to in that
session.** The live parent site is exactly how the owner wants it. Do not edit, "fix,"
refactor, or redeploy it — and specifically do not deploy `Frontends/lvl13.tech/` from this
repo, because that copy is the stale pre-migration trading clone and would overwrite the
correct live landing page. lvl13 is excluded from parity, stabilization, and de-duplication
work by default. If a backend change would affect the endpoints lvl13 depends on
(`/public/tracker/state` and `/contact`), call it out, but still touch lvl13's own files only
on explicit instruction.

---

## When You're Stuck or the Goal Is Ambiguous

Ask one clear question rather than guessing. A wrong guess here costs more than a
question, because the owner can't easily review the code to catch it.

---

## The Recovery Order (don't skip ahead)

1. See the truth — run the regression checklist on the 3 product sites (and lvl13's
   cross-site rollup section separately).
2. Confirm wallstbots.tech as the reference.
3. Get the reference site 100% working. Don't touch the others.
4. Commit/tag it as the known-good baseline.
5. Bring the other two product sites (aistocks, bitbot13) to parity, one at a time,
   verifying after each. Remember bitbot13's allowed differences: crypto asset class +
   crypto trading hours.
6. Verify lvl13's cross-site rollup still reads all three correctly.
7. De-duplicate into shared code (the permanent fix).
