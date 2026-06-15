# REGRESSION_CHECKLIST.md — Prove Each Site Still Works

**Purpose:** This is your "did I break anything?" test. You don't read code, so this is
how you (or Claude) verify a site works — by *using* it and checking each item.

**How to use it:**
- **Before** a change: run the checklist on the affected site so you know what already worked.
- **After** a change: run it again. Anything that went from ✅ to ❌ is a regression — the
  change broke something that was working. Stop and fix that before moving on.
- Run it on **all three product sites** (wallstbots, aistocks, bitbot13) when you change a shared-type file (parity check). lvl13 is the parent site — it is NOT part of this checklist; only run the small read-only lvl13 check at the bottom.

Mark each item: ✅ works · ❌ broken · ❔ not tested. Copy this block per site.

---

## How to run each item

Most items are just "open the page and look." Where a login is needed, use a test
account. For each site, open it in a normal browser tab and also open the browser
**Console** (F12 → Console) — a red error there usually explains a broken item.

---

## CHECKLIST — run once per site

> Site under test: __________________  ·  Date: __________  ·  Tester: __________

### A. Public pages (no login)
- [ ] Homepage loads with no red errors in the Console
- [ ] Live Leaderboard strip shows the 5 funds with a % change (not blank, not "NaN")
- [ ] "The Race" shows 5 fund cards with a dollar value and P&L
- [ ] Performance chart draws a line (not empty)
- [ ] Signals section shows buy/hold/sell counts and a table
- [ ] News shows headlines **on-topic only** (crypto site = no stock news; stock site = no crypto)
- [ ] Reports page lists weekly reports; clicking one opens its detail
- [ ] Clicking a single fund (Bot13/Oracle/Wizard) opens its page with a holdings table
- [ ] Footer "Also from Level 13" links point to the other sites
- [ ] Chatbot opens, quick-reply buttons appear, and typing a question gives an answer

### B. Navigation / routing
- [ ] Every nav link goes to the right section
- [ ] `#/login` link goes to the login page (NOT the homepage)
- [ ] `#/signup` link goes to the signup form (NOT the homepage)
- [ ] Back/forward browser buttons don't break the page

### C. Account flow (Flow A)
- [ ] Signup with a new email succeeds
- [ ] Login with that email succeeds and lands on the dashboard
- [ ] Dashboard shows the logged-in user's bots/portfolios (or an empty state, not an error)
- [ ] Refreshing the page keeps you logged in
- [ ] Logout works and returns you to a logged-out state
- [ ] Visiting the dashboard while logged out redirects to login (doesn't show a blank/error)

### D. Money flow
- [ ] "Get Yours" pricing shows correct tiers (confirmed in `app.js` `TIER_META`, monthly/annual toggle): FREE $0 (1 portfolio) · MEMBER $49.99/mo or $499/yr (5) · INSIDER $69.99/mo or $699/yr (10) · SYNDICATE $99.99/mo or $899/yr (25, "popular"). Recurring subscription, not the old one-time $799.
- [ ] Promo code field validates a known code (e.g. `levelUp13` — VERIFY current code)
- [ ] Referral code field accepts/validates a code
- [ ] **Stripe** checkout button/section appears and starts a Stripe Checkout session (don't complete a real purchase during testing). Checkout is Stripe, not PayPal.
- [ ] Stripe billing portal: "Manage Billing" / "Cancel Subscription" call `openStripePortal()` and open the portal (was once missing on wallstbots — check all three)

### E. Admin
- [ ] Admin login works on this site
- [ ] Admin panel loads data (doesn't show "unauthorized" for a real admin)

### F. Simulation data freshness (Flow B)
- [ ] The "last refresh" timestamp on the homepage is recent (within the expected cron window)
- [ ] Fund values changed since the previous trading day (data is actually updating, not frozen)

---

## Cross-site parity spot-check (after changing any shared file)

Do this quick pass on **all three product sites** after editing `auth.js`, `api.js`, `app.js`,
`login.html`, `dashboard.html`, `admin.html`, `bot-detail.html`, or a `refresh_*.py`:

- [ ] Login works on wallstbots
- [ ] Login works on aistocks
- [ ] Login works on bitbot13
- [ ] The thing you just changed behaves identically on all three (only branding — and, for
      bitbot13, the crypto asset class/hours — differ)

If it works on one site but not another, that's the classic drift bug — the change
didn't reach every copy. Apply it to the missing copies.

## lvl13.tech check (read-only — do NOT edit lvl13)

- [ ] lvl13.tech landing page loads
- [ ] The Bot13 P&L box shows a number (it reads `/public/tracker/state` for all 3 product sites)
- [ ] Contact form submits

If the lvl13 P&L box breaks, the cause is almost always a backend `/public/tracker/state`
change — fix it on the backend, not on lvl13.

---

## When something is ❌

1. Note exactly which item and which site.
2. Open the Console (F12) and copy any red error text.
3. Give Claude: the site, the broken item, and the error text. That's usually enough to
   locate the cause fast — much faster than "the site is broken."
