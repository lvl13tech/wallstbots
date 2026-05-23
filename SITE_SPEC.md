# Level 13 Sites — Master Spec & Parity Checklist

**Last updated:** 2026-05-20
**Owner:** Level 13 Tech
**Purpose:** Single source of truth for what each section on each site must do, so any future change can be checked across all three sites at once.

---

## 1. The Three Sites — What Each One Is

**Core rule (user-stated):** All three sites are IDENTICAL in layout, sections, auth, and admin. The only difference is the asset class they simulate trades for.

| Site | Asset Class | Universe |
|------|-------------|----------|
| **lvl13.tech** | AI & Quantum stocks | 43 hand-picked AI/quantum names |
| **bitbot13.tech** | Cryptocurrency | Top 50 by market cap |
| **wallstbots.tech** | Sector stocks | Top 3 per S&P 500 sector + IPOs (~55) |

All three sites share:
- The same SPA shell (`index.html` + `assets/app.js` + `assets/style.css`)
- The same nav, hero, sections, footer, and chatbot
- The same auth system (`auth.js`, `login.html`, `dashboard.html`, `admin.html`)
- The same backend (`https://wallstbots-backend-868128114349.us-east1.run.app`)
- The same JWT tokens (a login on one site logs the user in on all three)
- The same subscription / sales database (a sale on one site counts as a sale across the network, with origin tracked)

**Critical rule:** Any architectural change to one site MUST be ported to the other two. If something works on one site and doesn't on another, that's a parity bug to fix.

---

## 2. Shared Auth & Account Infrastructure (all 3 sites)

These files MUST be functionally identical across sites; only branding/strings differ.

| File | Purpose | Must Have |
|------|---------|-----------|
| `auth.js` | JWT login, signup, refresh, logout, storage | `signup()`, `login()`, `logout()`, `getToken()`, `setToken()`, `getUser()`, `isAuthenticated()`, `isTokenExpired()`, `refreshTokenIfNeeded()` |
| `login.html` | Login + signup forms | Posts to `/auth/login` and `/auth/signup` backend endpoints |
| `dashboard.html` (lvl13 = `index.html`) | Post-login portfolio dashboard | Lists user's bots, redirects to `/login` if unauthenticated |
| `admin.html` | Admin panel | `getToken()` reads `<site>_jwt` then falls back to `auth_token` |

**JWT storage key per site:** `lvl13_jwt`, `bitbot13_jwt`, `wallstbots_jwt` (with `auth_token` legacy fallback in admin)

---

## 3. SPA Site Sections (bitbot13 + wallstbots)

Both SPA sites share `app.js` architecture. Differences are topical (crypto vs. stocks), never structural.

### Section: Header & Nav
- Logo (links to `#/`)
- Hamburger menu (mobile)
- Nav links: News, How It Works, The Race, Bot13, Oracle, Wizard, Signals, Reports, Get Yours
- Auth-aware: shows **Log In** when no token, **Dashboard** when token present (handled by `updateNavAuthState()`)

### Section: Homepage (`renderHome` — route `/`)
1. **Hero** — robot image, headline ("5 strategies. N coins/stocks. Watch them race."), 2 CTAs
2. **Live Leaderboard** strip — 5 fund cards with today's % change
3. **Signals Today** — 3 columns: TOP BUYS, HOLDS, TOP SELLS
4. **News Today** — 5 latest filtered headlines
5. **The Race** — 5 fund cards with portfolio value + PnL
6. **Performance Trajectory chart** — line chart of all 5 funds over time
7. **Also from Level 13** cross-promo — 2 sibling-site cards
8. **Get Yours hint** — CTA strip

### Section: News-All (`renderNewsAll` — route `/news`, `/news-all`)
- Sector filter chips (ALL + per-sector categories)
- Grid of news cards (title, source, time, category color)
- Sales strip + 3 feature cards + Get Yours CTA

### Section: How It Works (`renderHowItWorks` — `/how`)
- 5 bot strip cards
- 3 feature cards (Daily B/S/H, Sunday Reports, Filtered News)
- Challenge panel + Get Yours CTA

### Section: The Race (`renderRace` — `/race`)
- 5 fund cards
- Performance Trajectory chart
- Get Yours CTA

### Section: Individual Fund (`renderFund(fid)` — `/fund/<id>`)
- Fund header (icon + name + tagline)
- 3 stat cards: Current Value, Total PnL, Today's Change
- Strategy panel (for bot13/oracle/wizard): today's picks with indicators
- Holdings table (Symbol, Units/Shares, Entry, Price, Value, Today%, PnL, %)
- Get Yours CTA

### Section: Signals (`renderSignals` — `/signals`)
- 5 summary stat cards (Strong Buy → Strong Sell counts)
- Filter chips (ALL + 5 actions)
- Full table (Symbol, Action, Price, Target, Upside, Score, Conf, Risk, RSI, 5d, 20d)
- "How signals are computed" explainer

### Section: Reports (`renderReports` + `renderReport(weekEnd)` — `/reports`, `/report/<date>`)
- Grid of weekly report cards (grade per fund)
- Detail view: 5 fund cards with narrative + grade + P&L

### Section: Get Yours (`renderGetYours` — `/get-yours`)
- Hero
- Plan selector (Monthly / Annual toggle)
- Pricing cards (1st portfolio / additional)
- Referral code input + validation
- PayPal subscription form
- Feature grid (6 cards)
- Footer with referral pitch

### Section: Thanks (`renderThanks` — `/thanks`)
- Confirmation + share-your-referral CTA

### Section: Referral (`renderReferral` — `/referral`)
- Hero
- How It Works (3 cards)
- Discount panel
- $35 credit panel
- Live referral dashboard (when logged in) — calls `/account/referral` endpoint
- Get Yours CTA

### Section: Chatbot (FAQ bot)
- Toggle button (bottom-right)
- Panel with welcome message, quick-reply chips (Pricing, Coins/Stocks, Bots, Cancel, Contact), text input
- `botAnswer()` matches keywords against the `FAQS` array

### Section: Footer
- Brand mark
- Nav links + email
- "Also from Level 13" tri-site link strip
- Copyright + disclaimer + contact

### Section: Hash Routes (router)
Every route in `route()`. The router MUST also redirect:
- `#/login` → `/login.html`
- `#/signup` → `/login.html#signup`

---

## 4. Topic Boundaries — News Filtering

This is non-negotiable for the user. Each site shows only news relevant to its universe.

| Site | Topic | Allowed sources | Excluded terms |
|------|-------|-----------------|----------------|
| **bitbot13** | Cryptocurrency only | CoinDesk, CoinTelegraph, Decrypt, The Block, Bitcoin Magazine, U.Today, BeInCrypto, Crypto Briefing | "stocks", "equities", "S&P 500", "Dow Jones" (unless co-occurring with crypto term) |
| **wallstbots** | Stock market only | Reuters Business, Bloomberg, WSJ, MarketWatch, CNBC, Yahoo Finance, Seeking Alpha, Barron's | "crypto", "bitcoin", "ethereum", "NFT", "blockchain", "Web3" |
| **lvl13** | AI & Quantum stocks only | Reuters Tech, Bloomberg Tech, MIT Tech Review, IEEE Spectrum, The Verge, Ars Technica, Nature, Nvidia/IonQ/Rigetti PR | "crypto", "bitcoin", "ethereum", and generic non-AI stocks |

**Implementation:** add a `domains` param to the NewsAPI request AND a post-fetch keyword filter that strips off-topic articles.

---

## 5. Data Pipeline (shared backend)

- **Backend:** `https://wallstbots-backend-868128114349.us-east1.run.app`
- **Public read endpoints:** `/public/tracker/{state,news,signals,reports}?platform={lvl13|bitbot13|wallstbots}`
- **Refresh scripts:** `Project/scripts/refresh_lvl13.py`, `refresh_bitbot13.py`, `refresh_wallstbots.py`
- **Pushed via:** `x-internal-key` header to `/internal/tracker/<type>?platform=<site>`
- **Cron:** GitHub Actions workflows in `.github/workflows/refresh-*.yml`

---

## 6. Verified Bugs Found in Current Codebase (2026-05-20)

These are the issues this spec drives fixes for.

### bitbot13.tech/assets/app.js
1. **`handleChatbotInput()` is called but never defined** (line 858) → chatbot text input crashes silently
2. **`chatbotRenderQuick()` is defined but never invoked** → quick-reply buttons stay empty
3. **`#/login` hash route is unhandled** → "Log in" links from referral page fall through to homepage
4. **`#/signup` hash route is unhandled** → same problem
5. **`admin.html` getToken** still reads only `auth_token`, missing the `bitbot13_jwt` fallback that wallstbots got

### lvl13.tech
1. **`index.html` is a logged-in dashboard**, not the SPA marketing/tracker shell. The SPA app.js already exists at `assets/app.js` (v3, with AI & Quantum content + routes for /customize, /setup, /my-tracker, /my-picks) but is never loaded because index.html points elsewhere. → Restore the SPA shell as index.html; move the current dashboard to dashboard.html.
2. **`admin.html` getToken** missing the `lvl13_jwt` fallback that wallstbots got
3. **`auth.js`** is older/more-verbose than the bitbot13/wallstbots version (same logic, just stale)
4. **`login.html`** is the old 6KB version (other two sites have the 11KB updated version with better UX)
5. **No `refresh_lvl13.py`** in Project/scripts/ — bitbot13 and wallstbots have refresh scripts that push state/news/signals/reports to the backend; lvl13 needs the same.

### wallstbots.tech
- Already has the JWT admin fix and the route redirects. Used as the reference for fixing the other two.

### Backend pipeline
- News scripts pull broadly via NewsAPI without source-restriction or negative-keyword filters → off-topic articles slip through.

---

## 7. Cross-Site Auth + Sales Sharing — Verified State

**Login (customer + admin):**
- The backend `/auth/login` endpoint accepts email + password, calls Supabase, returns a JWT. It does NOT check which site originated the request.
- The JWT is valid against every protected endpoint (`/user/*`, `/account/*`, `/admin/*`).
- `require_admin` only checks the user's `role` column, not the site of origin → admin login works on any site.
- **Limitation:** browsers scope `localStorage` to the site origin, so a JWT stored on `lvl13.tech` is not visible to JS on `bitbot13.tech`. The user must log in once per site (the credentials are the same). True cross-domain SSO would need a shared auth subdomain or redirect-based handoff — flagged for future work.

**JWT storage keys (per site):**
- `lvl13_jwt` (lvl13.tech)
- `bitbot13_jwt` (bitbot13.tech)
- `wallstbots_jwt` (wallstbots.tech)
- Admin pages on all 3 sites fall back to `wallstbots_jwt` then `auth_token` for legacy compatibility.

**Sales / subscriptions:**
- A subscription record (`subscriptions` table) is keyed on `user_id`, not on which site placed the order. So a customer who buys on bitbot13.tech is recognized as a paying customer on all 3 sites. ✅ Works as the user wants.
- **Gap (flagged for backend work):** the `subscriptions` table does NOT have an `origin_platform` column. So although sales are shared, you can't currently report "how many sales came from which site". To track origin, the backend schema needs an `origin_platform` column added and the `/paypal/webhook` insert updated to set it. This is recorded in section 9.

---

## 8. Parity Checklist (use before any commit)

Before merging any change that touches site code, check each row:

- [ ] If you changed `auth.js`, `login.html`, `dashboard.html`, or `admin.html` → did you make the same change on all 3 sites?
- [ ] If you changed `app.js` on bitbot13 → did you mirror it to wallstbots (with topical word swaps)?
- [ ] If you added a hash route → is it handled in `route()` on both SPA sites?
- [ ] If you added a function reference in `wireUI()` or HTML inline → is that function actually defined in the file?
- [ ] If you changed news queries → did you keep bitbot13 = crypto-only and wallstbots = stocks-only?
- [ ] If you changed pricing or PayPal config → did you update all 3 `renderGetYours()` blocks?
- [ ] If you changed the JWT key naming → did you update admin.html's `getToken()` fallback on all 3 sites?

---

## 8. File Reference Map

```
WallStBots/
├── Backend/                         # FastAPI service (Cloud Run)
│   └── main.py                      # ES256 JWT, /auth, /public/tracker, /internal/tracker, /admin
├── Frontends/
│   ├── lvl13.tech/                  # Account hub + AI & Quantum dashboard
│   │   ├── index.html               # Post-login bot dashboard
│   │   ├── login.html, signup.html  # Auth pages (stale — needs sync)
│   │   ├── admin.html               # Admin panel (needs JWT fallback fix)
│   │   ├── auth.js, api.js          # Auth client + API wrapper
│   │   └── assets/                  # Logo, favicon, CSS
│   ├── bitbot13.tech/               # Crypto SPA marketing/tracker site
│   │   ├── index.html               # SPA shell
│   │   ├── login.html, dashboard.html, admin.html
│   │   ├── auth.js
│   │   └── assets/app.js            # ~60KB SPA (needs chatbot/route fixes)
│   └── wallstbots.tech/             # Stocks SPA marketing/tracker site (REFERENCE)
│       ├── index.html               # SPA shell
│       ├── login.html, dashboard.html, admin.html  (has JWT fix)
│       ├── auth.js
│       └── assets/app.js            # ~62KB SPA
└── Project/scripts/
    ├── refresh_lvl13.py
    ├── refresh_bitbot13.py          # Needs crypto-only news filter
    ├── refresh_wallstbots.py        # Needs stocks-only news filter
    └── seed_tracker_db.py
```

---
