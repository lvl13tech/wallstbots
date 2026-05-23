# WallStBots — Business Model & Product Vision

**Owner:** Jamil Flowers (M13) · lvl13cs@gmail.com  
**Last updated:** May 2026  
**READ THIS FIRST in every session. Every decision must be made with paying customers in mind.**

---

## What We Are Building

A **multi-brand AI trading tracker SaaS**. Customers pay to get their own personalized version of the bot portfolio tracker — with the same 5 bots trading on their chosen stocks or crypto.

The three public-facing sites are **marketing demos** — they show M13's own live picks so prospective customers can see real performance before buying.

---

## The Three Sites (Marketing / Demo)

| Site | Universe | Purpose |
|------|----------|---------|
| **wallstbots.tech** | 55 stocks (full market) | Shows stock trading bots in action |
| **bitbot13.tech** | 50 crypto coins | Shows crypto trading bots in action |
| **lvl13.tech** | 43 AI & Quantum stocks | Shows niche/themed tracker — proves any segment works |

**lvl13.tech is the proof of concept for the upsell:** "Look — I built one just for AI and quantum stocks. You can have one built around whatever you care about most."

### Customer flow
1. Customer lands on any site → sees live bot performance (updated automatically)
2. Sees real P&L, real signals, real news — all running on their own
3. Thinks: "I want this for MY stocks" → clicks **GET YOURS**
4. Purchases a tracker → gets their own dashboard with their own picks

---

## Pricing

| Tier | Annual | Monthly |
|------|--------|---------|
| **1st portfolio** | $799 / year | $79.99 / month |
| **Each additional portfolio** | $299 / year | $29.99 / month |

**Goal: sell multiple portfolios per customer.**  
- Customer buys stocks tracker → upsell crypto tracker ($299 more)  
- Customer buys stocks + crypto → upsell AI/Quantum themed tracker ($299 more)  
- Each additional tracker is cheap enough that most customers will add one

---

## What the Customer Gets

After purchase, the customer receives:
- Their **own dashboard** running the same 5 bots (BOT13, ORACLE, WIZARD, EQUALIZER, TITAN)
- Bots trade on the **customer's chosen stocks or crypto** (not M13's picks)
- **Single login** across all their trackers (one account, one payment)
- Access gated by what they paid for — stocks access, crypto access, or both
- Live updates: prices, signals, news — refreshed automatically (no manual work)

**Customers do NOT pick their own stocks manually** — they choose a universe/theme and the bots handle the trading decisions automatically.

---

## The 5 Bots (identical across all sites)

| Bot | Strategy | Timeframe |
|-----|----------|-----------|
| **BOT13** | Intraday momentum — top 5 movers | Daily |
| **ORACLE** | Composite momentum — top 5 names | Weekly (Monday) |
| **WIZARD** | Long-horizon trend | Monthly |
| **EQUALIZER** | Equal-weight baseline | Continuous |
| **TITAN** | Cap-weighted — half on heavyweights | Continuous |

---

## Revenue Architecture

- **One payment processor account** (PayPal, `lvl13cs@gmail.com`) handles all purchases
- **One login system** — customer authenticates once, sees all their trackers
- Stocks and crypto are **separate purchases** — customer pays for what they want
- Backend scopes data by `platform` — `wallstbots`, `bitbot13`, `lvl13`

---

## Automation Requirement (NON-NEGOTIABLE)

> "Everything needs to run automatically. Customers are paying — they can't see stale data."

- Data refreshes via **GitHub Actions** (cloud cron jobs — no local machine needed)
- wallstbots.tech: refreshes **twice on weekdays** (market open + market close)
- bitbot13.tech: refreshes **every 4 hours** (crypto never closes)
- lvl13.tech: refreshes **on the GCP VM** (existing cron setup)
- On every refresh: prices → P&L → BOT13 picks → signals → news → GitHub push → Cloudflare Pages deploys

---

## What NOT to Build (Anti-patterns)

- ❌ Anything that requires M13 to manually run a script
- ❌ Anything that breaks if M13's laptop is off
- ❌ Hard-coded data / placeholder prices — everything must be live
- ❌ Separate backends per site — one backend, platform-scoped
- ❌ Building features before the core loop (live data → auto deploy) is solid

---

## Technical Stack (Summary)

- **Frontend:** Static HTML/CSS/JS → Cloudflare Pages (auto-deploys on GitHub push)
- **Data:** Static JSON files in `Frontends/*/data/` — fetched by the frontend
- **Refresh:** GitHub Actions cron → Python (yfinance + NewsAPI) → commits JSON → Cloudflare deploys
- **Backend:** Cloud Run (`wallstbots-backend`) on GCP — handles user auth, subscriptions, per-customer data
- **DB:** Supabase (Postgres) via Cloud Run — stores user picks, subscriptions, tracker state
- **Payments:** PayPal subscription webhooks → Cloud Run → provision customer tracker

---

## Next Phase (Customer Provisioning)

When a customer pays:
1. PayPal webhook fires → Cloud Run `/internal/provision`
2. Backend creates a customer row in Supabase
3. Customer gets a login + dashboard URL
4. Their tracker starts running using the same bots on their chosen universe

This is the **automated provisioning** system — no human touch after payment.

---

## Key Insight for Every Decision

> The three demo sites need to look GREAT and show REAL data at all times.  
> That's what converts visitors into paying customers.  
> If the data is stale, wrong, or missing — we lose the sale.
