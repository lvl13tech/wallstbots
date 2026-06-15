# SESSION_START.md — Paste This First, Every New Chat

> **How to use:** at the start of every new Claude session about this project, paste this whole file in as your first message. It gives Claude the global context it loses between chats. Then say what you want done.

---

## Read these files before changing anything

1. `ARCHITECTURE.md` — how the four sites connect and how data flows
2. `PROJECT_STATUS.md` — what currently works and what's broken
3. `CLAUDE.md` — the rules you MUST follow when editing this repo
4. `SITE_SPEC.md` — detailed per-section spec + parity checklist
5. `REGRESSION_CHECKLIST.md` — the test to run before and after any change

---

## The 60-Second Project Summary

**What it is:** Four domains in two tiers. **Three product sites** *simulate* trading, each a
near-identical clone covering a different asset class: **wallstbots** = sector stocks,
**aistocks** = AI/quantum stocks, **bitbot13** = crypto (and only bitbot13 runs crypto
trading hours instead of equity market hours). The **fourth site, lvl13.tech, is the parent
company** (the SaaS firm that owns the Wall St Bots platform) — strictly a corporate/marketing
landing page, NOT a trading product: no pricing, no Stripe, no signup. Its ONLY cross-site
data use is the **BOT13 P&L text box**. (Note: the repo's lvl13 app.js is still the old
pre-migration trading clone and hasn't been reconciled to this yet — see ARCHITECTURE.md §0.)
All four share one login and one backend.

> Why this is easy to get wrong: aistocks.tech *used to be* lvl13.tech. The AI/quantum
> trading site was migrated lvl13 → aistocks, then lvl13 was rebuilt as the parent company.
> Old comments still say "lvl13 = AI/quantum" — that's now aistocks. Source of truth: the
> backend whitelist `("aistocks", "bitbot13", "wallstbots")`.

**Architecture:** 4 frontends → 1 FastAPI backend (Google Cloud Run) → 1 Supabase Postgres database. Python "refresh" scripts run on a schedule, simulate five trading bots, and push results to the backend. The product sites only read that data; lvl13 reads a cross-site rollup of it. (Backend: `https://wallstbots-backend-868128114349.us-east1.run.app`)

**Current status:** BROKEN. No site is fully working. See `PROJECT_STATUS.md`.

**Why it keeps breaking:** The product sites were *cloned*, not built from shared code. There are three separate copies (wallstbots, aistocks, bitbot13) of `auth.js`, `api.js`, `app.js`, the auth HTML pages, and the refresh scripts. A fix to one copy doesn't reach the others, so they drift apart and "fixing one breaks another." **wallstbots.tech is the reference site (most up to date).** lvl13 (the parent site) is outside this parity set.

**The goal right now:** NOT new features. Get ONE site fully working, lock it as a known-good baseline, bring the others to parity one at a time, then de-duplicate into shared code so this never happens again.

---

## The Non-Negotiable Rules (full version in CLAUDE.md)

1. **Smallest change.** Make the smallest possible change that achieves the goal. Don't refactor unrelated code while fixing a bug.
2. **Test first, then fix.** Before changing anything, write/confirm the checklist that proves what currently works. Don't apply a fix until we agree on what "still working" means.
3. **Parity.** If you change a shared-type file (`auth.js`, `api.js`, `app.js`, `login.html`, `dashboard.html`, `admin.html`, `refresh_*.py`), you must apply the same change to ALL THREE PRODUCT-SITE copies (wallstbots, aistocks, bitbot13) in the same change, or explicitly tell me you're only doing one and why. lvl13 (parent site) is not in this set — only touch it for the shared backend contract or its cross-site rollup.
4. **Explain like I'm not a coder.** I vibe-code. For every change, tell me in plain English: what you changed, why, what could it affect, and how I verify it works.
5. **Frontends don't decide.** No prices, discounts, or business rules in HTML/JS. That logic lives in the backend.
6. **Long-term health over quick fixes.** Always do what's best for the platform and paying members, even if it's slower.

---

## What I want you to do this session

> (Write your actual request here when you paste this in. Example: "Run the regression checklist on wallstbots.tech and tell me exactly what's broken — don't fix anything yet.")
