# ARCHITECTURE.md — How the Level 13 Platform Fits Together

**This is the source of truth for how the sites connect and how data flows.**
If anything in the code contradicts this file, that is a bug — fix the code or update this file deliberately, never silently.

Last updated: 2026-06-15 · Owner: Jamil Flowers (M13)

---

## 0. The Two-Tier Mental Model (read this first)

There are **four domains**, but they are NOT four peers. They split into two tiers:

**Tier 1 — The Wall St Bots product (3 sites).** These are the actual trading-simulation
product. They are near-identical clones of each other:

- **wallstbots.tech** — sector/broad-market stocks. **The reference site (most up to date).**
- **aistocks.tech** — AI & quantum stocks.
- **bitbot13.tech** — crypto. The ONE site that genuinely differs: it simulates crypto and
  runs on crypto trading hours/sessions instead of equity market hours.

All three are functionally identical *except* for (a) the asset universe each simulates on
its homepage, and (b) bitbot13's crypto asset class + trading hours. Everything else —
login, dashboard, admin, member section — is the same code cloned per site.

**Tier 2 — The parent company (1 site).** **lvl13.tech** is the SaaS tech company (JBM
Capital LLC) that *owns* the Wall St Bots platform. It is **strictly a corporate/marketing
landing page** — NOT a fourth trading site. No login, no router, no pricing, no
Stripe/checkout, no signup, no tracker/dashboard. It runs no trading simulation.

**🔒 DO NOT MODIFY lvl13.tech unless the owner explicitly tells you to.** The live site is
exactly how the owner wants it. It is out of scope for all product-site/parity/stabilization
work by default.

**The live lvl13.tech (verified against the running site 2026-06-15):** a single inline
single-page site (logic is inline in the HTML — there is no separate `app.js`; the only
external script is Cloudflare's beacon). Sections: hero with a ticker strip, a "Wall St.
Bots ecosystem" section that links out to the three product sites, the **Bot13 engine
section with the live P&L box**, a stats band, a custom-development services section, a
contact form, and a support chatbot.

**Its entire backend surface is 4 calls — nothing else:**

1. `GET /public/tracker/state?platform=wallstbots`
2. `GET /public/tracker/state?platform=aistocks`
3. `GET /public/tracker/state?platform=bitbot13`
   → these three feed the **BOT13 P&L text box** (Bot13's performance across all three
   product markets). lvl13 reads the `state` payload's `value.pnl` / `value.pnl_pct` fields.
   It does **NOT** call `?platform=lvl13` (that platform doesn't exist in the backend).
4. `POST /contact` — the contact form / chatbot lead capture.

So on the backend side, lvl13 needs only the public `state` read endpoint (already used by
the product sites) and the `/contact` endpoint. It needs **no** auth, pricing, Stripe, or
`lvl13`-platform tracker data.

> **Repo copy status (updated 2026-06-15):** lvl13.tech has been **disconnected from
> GitHub**, so there is no auto-deploy from this repo to the live site — the live landing
> page can only be changed on the host. The repo's `Frontends/lvl13.tech/` was a *mix*: the
> real current landing page (`index.html` + `assets/style.css` + svgs) sitting on top of
> leftover pre-migration trading-clone files (`auth.js`, `api.js`, `assets/app.js`,
> `login/dashboard/admin/signup/leaderboard/bot-detail` pages, and `data/*.json`). The
> trading-clone leftovers are being removed (`CLEANUP-lvl13-leftovers-doubleclick-me.bat`);
> `index.html` + `style.css` are **kept as the only local copy of the live landing page**
> (note: a few referenced image assets like `hero-bg.png` / `logo-*.png` are not in the repo,
> so the local copy renders without images — fine, since this repo is never deployed to
> lvl13). Recommended: pull a full backup of the live site (including images) down from the
> host, since no off-host copy currently exists.

> **Historical note (why the old docs/code are confusing):** aistocks.tech was originally
> lvl13.tech. That made no sense once lvl13 became the parent brand, so the AI/quantum
> trading site was **migrated from lvl13.tech → aistocks.tech**, and lvl13.tech was then
> rebuilt as the parent company website. Stale comments in `bot13_engine.py` and older docs
> still say "lvl13 = AI & quantum universe" — that universe now lives on **aistocks**, not
> lvl13. The authoritative, current truth is the backend platform whitelist:
> `("aistocks", "bitbot13", "wallstbots")` in `Backend/main.py` (`grant-access`). lvl13 is
> deliberately absent from that list because it is not a tradable platform.

---

## 1. The One-Sentence Version

Three near-identical trading-simulation websites (Wall St Bots: stocks, AI stocks, crypto)
plus one parent-company site (lvl13.tech) all talk to **one** backend, which reads/writes
**one** Postgres database. Trading data is *simulated* by Python "refresh" scripts that run
on a schedule, score a fixed universe of symbols, and push the results to the backend. The
product sites only ever *read* that data; lvl13 reads a cross-site rollup of it.

```
        ┌─ lvl13.tech ──────┐  (parent company; reads a cross-site rollup only)
        │                   │
PRODUCT ├─ wallstbots.tech ─┤──►  ONE FastAPI BACKEND  ──►  ONE Supabase Postgres DB
 (3)    ├─ aistocks.tech ───┤     (Google Cloud Run)        (users, bots, holdings,
        └─ bitbot13.tech ───┘            ▲                    performance, subscriptions)
           (crypto + crypto hours)       │
                               Python refresh scripts
                               (GitHub Actions cron) push
                               simulated prices/signals/news
```

Backend URL: `https://wallstbots-backend-868128114349.us-east1.run.app`

---

## 2. The Pieces (and what each is allowed to do)

| Piece | Lives in | Job | NOT allowed to |
|-------|----------|-----|----------------|
| **Product frontends** (3 sites) | `Frontends/<site>/` | Show simulated trading data. Log users in. Read from backend. | Contain business logic, pricing rules, or trading math. They only render. |
| **Parent site** (lvl13.tech) | `Frontends/lvl13.tech/` | Corporate/marketing for the parent company; render one cross-site rollup of the 3 product sites. | Run the trading simulation or act as a 4th product. It only displays a rollup. |
| **Backend** | `Backend/main.py` | The ONLY place business logic lives: auth, pricing, promo codes, serving tracker data, computing portfolio snapshots. | Be bypassed. No site should ever hardcode a price, a discount, or a rule the backend owns. |
| **Database** | Supabase Postgres (`Backend/schema.sql` + migrations) | Store everything: users, bots, holdings, performance, subscriptions, promo codes. | Be written to directly by a frontend. |
| **Refresh scripts** | `Project/scripts/refresh_*.py` | Simulate trading. Fetch live prices (yfinance), run bot strategies, push results to backend. | Each be a separate copy of the same logic (see §6 — this is the current bug). |

**Golden rule:** A frontend never decides anything. The backend decides; the database remembers; the frontend displays. If you are tempted to put a number or a rule into a `.html` or `app.js` file, stop — it belongs in the backend.

---

## 3. The Two Data Flows (this is what "one data point affects another" actually means)

There are exactly **two** flows. Almost every bug is one of these two getting crossed.

### Flow A — Account & Money (user-driven, needs login)
```
User → Frontend (auth.js) → POST /auth/login → Backend → Supabase Auth
                                                  ↓
                                          returns JWT token
                                                  ↓
Frontend stores token in localStorage (per-site key, see §5)
                                                  ↓
Every later call sends  Authorization: Bearer <token>
                                                  ↓
Backend verifies token → Database Row-Level Security filters to that user → returns only their data
```
A login on ANY site works on ANY other site (same backend, same JWT). A purchase on any site counts platform-wide because subscriptions are keyed on `user_id`, not on which site sold it.

### Flow B — Simulated Trading Data (scheduled, no login)
```
GitHub Actions cron → runs refresh_<site>.py
        ↓
Script fetches live prices (yfinance) + 90-day history
        ↓
Script runs the 5 bot strategies (Bot13, Oracle, Wizard, Equalizer, Titan)
        ↓
Script POSTs results to backend:  /internal/tracker/push  (header: x-internal-key)
        ↓
Backend stores it, also computes per-member portfolio snapshots
        ↓
Frontend reads it (no login):  GET /public/tracker/{state|signals|news|reports}?platform=<site>
```

**Where the two flows touch:** member portfolio simulations. The refresh script (Flow B) computes how each *paying member's* portfolio performed using the day's prices. That number then shows up in the member's logged-in dashboard (Flow A). This is the single most fragile junction in the system — treat changes here with extra care and always run the regression checklist after.

---

## 4. The Five Bots (the simulation engine)

Every site simulates the same five strategies against its own universe of symbols:

| Bot | Strategy | Recomputes |
|-----|----------|-----------|
| **Bot13** | Precision Intraday Momentum | 3× per trading day (open, midday, close) |
| **Oracle** | Adaptive Weekly Momentum | Every Monday |
| **Wizard** | Quality Monthly Momentum | 1st trading day of each month |
| **Equalizer** | Equal-weight baseline | Mark-to-market only |
| **Titan** | Top-10-weighted baseline | Mark-to-market only |

The actual scoring math lives in `bot13_engine.py` (shared) and inside each `refresh_*.py`. Universes differ per **product** site: wallstbots = sector stocks + IPOs, aistocks = AI/Quantum names, bitbot13 = top crypto. (lvl13 is the parent site and runs no simulation of its own — ignore the stale "lvl13 = AI & quantum" comment in `bot13_engine.py`; that universe migrated to aistocks.)

**Why this matters for stability:** the bots produce numbers that feed snapshots that feed leaderboards that feed the homepage and the member dashboard. A change to scoring ripples through all of those. That ripple is *expected* — what is NOT acceptable is a change to one site's engine silently diverging from the others'.

---

## 5. Per-Site Differences (the ONLY things allowed to differ)

The **three product sites** are intentionally identical except for these:

| Thing | How it differs | Where set |
|-------|----------------|-----------|
| Asset class / universe | The list of symbols (stocks / AI stocks / crypto) | `UNIVERSE` in each `refresh_*.py` |
| Trading hours / session | **bitbot13 only** runs crypto hours; the two stock sites run equity market hours | `CRYPTO_CFG` vs `EQUITY_CFG` in `bot13_engine.py` |
| Branding (logo, colors, copy) | Strings and assets only | `assets/`, HTML text |
| News topic filter | crypto-only / stocks-only / AI-only | `refresh_*.py` news section |
| localStorage JWT key | `aistocks_jwt`, `bitbot13_jwt`, `wallstbots_jwt` | `auth.js` (the key strings) |

**Everything else must be functionally identical across the three product sites.** If
`auth.js` logic differs between two of them, that is drift, and drift is the root cause of
the "fix one, break another" problem (see §6).

**lvl13.tech is not part of this parity set.** It is the parent company site. It does not run
the simulation and is not a tradable platform (it's absent from the backend whitelist
`("aistocks", "bitbot13", "wallstbots")`). Its only data dependency is the cross-site rollup
section that reads the three product sites — keep that in mind, but do not try to force lvl13
into parity with the product sites.

---

## 6. KNOWN STRUCTURAL PROBLEM — Read This Before Touching Anything

The product sites were built by **cloning** the first working site. That means the shared
files are not actually shared — there are separate copies per product site:

- `Frontends/wallstbots.tech/auth.js`
- `Frontends/aistocks.tech/auth.js`
- `Frontends/bitbot13.tech/auth.js`

…and the same duplication for `api.js`, `assets/app.js`, `login.html`, `dashboard.html`,
`admin.html`, and the `refresh_*.py` scripts. (lvl13.tech also has its own copies of the
shared chrome where it reuses login/branding, but it is the parent site, not a product
clone — do not bring it to product-site parity.)

**This is why fixing one site breaks (or fails to fix) another.** A change applied to one
copy does not reach the others. They drift apart until nothing is consistent.

**The long-term fix (the right way, per platform-health priority):** collapse the duplicates into a single shared source that all sites import — one `auth.js`, one `api.js`, one `app.js` (with per-site config), and one parameterized refresh engine instead of four scripts. Until that refactor happens, the **Parity Rule** in `CLAUDE.md` is mandatory: any change to a shared-type file must be applied to all copies in the same change, and verified with `REGRESSION_CHECKLIST.md`.

---

## 7. Where Everything Lives

```
WallStBots/
├── ARCHITECTURE.md          ← THIS FILE (how it all connects)
├── PROJECT_STATUS.md        ← what works / what's broken right now
├── SESSION_START.md         ← paste this at the start of every Claude chat
├── CLAUDE.md                ← rules Claude must follow when editing this repo
├── REGRESSION_CHECKLIST.md  ← click-through test for all 4 sites
├── SITE_SPEC.md             ← detailed per-section spec + parity checklist (existing)
├── Backend/
│   ├── main.py              ← the entire backend (auth, tracker, pricing, admin)
│   ├── schema.sql           ← database structure
│   └── *_migration.sql      ← incremental DB changes
├── Frontends/
│   ├── wallstbots.tech/     ← PRODUCT: sector stocks (the REFERENCE site — most up to date)
│   ├── aistocks.tech/       ← PRODUCT: AI & quantum stocks (was originally lvl13.tech)
│   ├── bitbot13.tech/       ← PRODUCT: crypto (different asset class + crypto trading hours)
│   └── lvl13.tech/          ← PARENT COMPANY site (not a product; has a cross-site rollup section)
└── Project/scripts/
    ├── refresh_wallstbots.py
    ├── refresh_aistocks.py
    ├── refresh_bitbot13.py
    ├── refresh_portfolios.py ← member portfolio simulation (shared, the fragile junction)
    └── bot13_engine.py       ← shared scoring engine (equity + crypto configs)
```

---

## 8. The Contract Between Sites (what must never change without coordination)

These are the shared "interfaces." If you change one side, you must change the other:

1. **Tracker data shape** — what `refresh_*.py` pushes must match what `app.js` reads. Fields like `funds`, `snapshots`, `leaderboards`, `value.total`, `value.pnl_pct`, `positions[]` are a contract. Renaming one in the script without updating every site's `app.js` breaks the display.
2. **Auth endpoints** — `/auth/login`, `/auth/signup`, `/auth/refresh` and the JWT shape. `auth.js` on all three product sites depends on these. (lvl13 has no auth.)
3. **Public read endpoints** — `/public/tracker/{type}?platform=<site>`. The three product sites call these for their own data; **lvl13 also calls `/public/tracker/state` for all three** to feed its Bot13 P&L box, plus `POST /contact`.
4. **JWT storage keys** — listed in §5. Admin pages fall back through `<site>_jwt` → `wallstbots_jwt` → `auth_token`. (Product sites only.)

When you touch any of these four, say so out loud and check every consumer.
