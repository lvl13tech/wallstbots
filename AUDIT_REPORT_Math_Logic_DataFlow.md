# WallStBots Platform — Mathematical Logic & Data Flow Audit
**Scope:** lvl13.tech · wallstbots.tech · bitbot13.tech  
**Files Audited:** `Frontends/lvl13.tech/assets/app.js`, `dashboard.html`, `portfolio-fund.html`, `Backend/main.py`, `data-flow-diagram.html`  
**Phases Completed:** 1 (Extraction), 2 (Cross-page trace), 3 (Discrepancies), 4 (Confirmed alignments)

---

## PHASE 1 — Variable & Equation Map

### Core Portfolio Math

| Equation | Location | Formula |
|---|---|---|
| Starting capital (member) | `portfolio-fund.html:496` | `holdings.length × 1000` |
| Starting capital (global fallback) | `app.js:343` | `STATE.funds.starting_capital \|\| 50000` |
| Starting capital (fund card fallback) | `app.js:156` | `{ total: 50000 }` |
| Gain/Loss $ | Backend `bot_fund_state` | `total_value − entry_cost` |
| Gain/Loss % | Backend `bot_fund_state` | `gain_loss / entry_cost × 100` |
| Day P&L $ | Backend `bot_fund_state` | `total_value × (day_pct / 100)` |
| Position shares (fallback) | `portfolio-fund.html:600` | `1000 / entry_price` |
| Position value (fallback) | `portfolio-fund.html:601` | `shares × price` |
| Position P&L $ (fallback) | `portfolio-fund.html:602` | `value − 1000` |
| Position P&L % (fallback) | `portfolio-fund.html:603` | `(price / entry_price − 1) × 100` |
| Position day P&L (fallback) | `portfolio-fund.html:605` | `value × dayPct / 100` |
| Max portfolio value | `app.js` constants | `50 × $1,000 = $50,000` |
| Performance snapshot rounding | `main.py:1569-1570` | `round(total_value, 2)`, `round(gain_loss_pct, 4)` |

### Subscription Pricing

| Tier | Monthly | Annual | Savings |
|---|---|---|---|
| Member | $49.99 | $499.00 | ~17% |
| Insider | $69.99 | $699.00 | ~17% |
| Syndicate | $99.99 | $899.00 | ~25% |

**Referral discounts:**
- Monthly: `price × 0.5` (50% off first month)
- Annual: `price − 100` ($100 off)
- Referrer credit: `+$35` to `referral_credit_balance`

**Webmaster pricing (Build Your Own):**
- `base_price = 799.00` (1 bot) or `799.00 + (bot_count − 1) × 349.00`
- Referral discount in this flow: `+$75.00` flat (different from subscription referral!)

### Bot Cash Window Logic

| Bot | In-Window Condition | Formula |
|---|---|---|
| BOT13 | Market hours | `day ∈ {0,6}` OR `minuteOfDay < 570` OR `minuteOfDay >= 960` |
| ORACLE | Weekly cycle | `day === 0` OR (`day === 6` AND `minuteOfDay >= 181`) OR (`day === 1` AND `minuteOfDay < 570`) |
| WIZARD | Monthly cycle | Always `false` (never in cash window — holds full month) |

### Signal Score Thresholds

| Signal | Threshold |
|---|---|
| Strong Buy | score ≥ +12 |
| Buy | score ≥ +4 |
| Sell | score ≤ −4 |
| Strong Sell | score ≤ −12 |

### Tier Portfolio Limits

| Tier | Max Portfolios | Frontend | Backend |
|---|---|---|---|
| free | 1 | ✓ | ✓ |
| member | 5 | ✓ | ✓ |
| insider | 10 | ✓ | ✓ |
| syndicate | 25 | ✓ | ✓ |
| webmaster | 99 | ✓ | ✓ |

---

## PHASE 2 — Cross-Page Data Flow Trace

### Chain: `bot_fund_state` → `portfolio-fund.html` → `dashboard.html`

| Field | DB Column | API Field | portfolio-fund renders as | dashboard renders as | Match? |
|---|---|---|---|---|---|
| `total_value` | `NUMERIC(14,2)` | `float` | `fmt$0(total)` = `$` + rounded int | `fmt$0(val.total)` | ✅ Same formatter |
| `gain_loss` | `NUMERIC(14,2)` | `float` | `fmt$0(pnl)` | Not directly shown in stat cards | ✅ |
| `gain_loss_pct` | `NUMERIC(10,4)` | `float` | `fmtPct(pnlPct)` = `.toFixed(2)+'%'` | `fmtPct(row.all_pnl >= 0)` (color) | ✅ |
| `day_pnl` | `NUMERIC(14,2)` | `float` | `fmt$0(dayPnl)` | `fmt$0(dayPnl)` | ✅ |
| `day_pct` | `NUMERIC(10,4)` | `float` | `fmtPct(dayPct)` | `fmtPct(day_pct)` | ✅ |

### Chain: Tracker API → Homepage fund cards → Homepage race

| Field | Tracker Source | fundCard fallback | renderRace fallback | Match? |
|---|---|---|---|---|
| `total` | `funds[fid].value.total` | `50000` | `49000` | ❌ **MISMATCH** |
| `pnl` | `funds[fid].value.pnl` | `0` | `0` | ✅ |
| `pnl_pct` | `funds[fid].value.pnl_pct` | `0` | N/A | ✅ |
| `starting_capital` | `STATE.funds.starting_capital` | — | `|| 49000` | ⚠️ (see Issue #1) |

### Chain: Subscription → Stripe Checkout → Webhook → DB tier

| Step | Formula | Correct? |
|---|---|---|
| Frontend shows price | `PRICING[tier][cycle]` | ✅ |
| Referral monthly preview | `price × 0.5` (frontend) | ✅ |
| Referral annual preview | `price − 100` (frontend) | ✅ |
| Stripe coupon monthly | `percent_off: 50` | ✅ matches frontend |
| Stripe coupon annual | `amount_off: 10000` ($100) | ✅ matches frontend |
| Webhook tier activation | `tier_map[meta.tier]` | ✅ |
| Referral credit posted | `+35` to DB | ✅ |
| Admin code validate endpoint | Returns correct `tier` from `ADMIN_CODE_TIERS` | ✅ (fixed at validate step) |
| Admin code signup endpoint | Returns hardcoded `"insider"` | ❌ **BUG** (see Issue #2) |

---

## PHASE 3 — Mathematical Discrepancy Report

---

### 🔴 ISSUE #1 — Starting Capital Default Mismatch (homepage race vs fund card)

**Location:**
- `app.js line 156` — `fundCard()` fallback
- `app.js line 343` — `renderRace()` fallback

**The Issue:**

`fundCard()` uses a hardcoded fallback of `$50,000` when tracker data is unavailable:
```javascript
// app.js line 156
const v = data && data.value ? data.value : { total: 50000, pnl: 0, pnl_pct: 0, day_pnl: 0, day_pct: 0 };
```

`renderRace()` uses a hardcoded fallback of `$49,000`:
```javascript
// app.js line 343
fmt$0((STATE.funds&&STATE.funds.starting_capital)||49000)
```

The data-flow-diagram explicitly documents that `lvl13.tech` starting capital is `$49,000`. The fund card fallback of `$50,000` contradicts both the diagram and the race fallback.

**Impact:** When tracker data is unavailable, the homepage fund cards display `$50,000` but the race panel displays `$49,000` for the same platform. A user seeing the loading state sees two different capital figures. Additionally, the fund card fallback is conceptually wrong — a portfolio with 50 holdings × $1,000 = $50,000 is the **maximum** portfolio capital, not the platform's starting capital.

**Recommended Fix:**
```javascript
// app.js line 156 — align to the actual platform starting capital
const PLATFORM_START = 49000;  // lvl13.tech — defined once, used everywhere
const v = data && data.value ? data.value 
        : { total: PLATFORM_START, pnl: 0, pnl_pct: 0, day_pnl: 0, day_pct: 0 };
```
And update `renderRace()` to use the same constant:
```javascript
fmt$0((STATE.funds&&STATE.funds.starting_capital) || PLATFORM_START)
```

> **Note:** Each platform has a different starting capital (`wallstbots=$55,000`, `bitbot13=$50,000`). These constants must be set per-platform in each site's respective `app.js`.

---

### 🔴 ISSUE #2 — Admin Code Signup Hardcodes Wrong Tier

**Location:** `Backend/main.py` — `/auth/signup-with-admin-code` endpoint (approx. line 607)

**The Issue:**

The `/subscriptions/validate-referral` endpoint correctly returns the tier from `ADMIN_CODE_TIERS`:
```python
# main.py — validate-referral endpoint (correct)
admin_tier = ADMIN_CODE_TIERS.get(code.lower(), 'insider')
return { "tier": admin_tier, ... }
# admin13 → 'insider', adminm13 → 'syndicate' ✅
```

But the `/auth/signup-with-admin-code` endpoint that **actually creates the account** returns a hardcoded `"insider"` regardless of which code was used:
```python
# main.py ~line 607 — signup endpoint (BUG)
return { ..., "tier": "insider", ... }  # always 'insider', even for adminm13
```

**Impact:** A user who applies `adminm13` (the syndicate-level admin code) is told they have INSIDER access on the validate step, then signs up expecting SYNDICATE, but the DB activation writes `"insider"`. The user is silently under-privileged — they can only create 10 portfolios instead of 25, and the account cannot be corrected without a manual DB update.

**Recommended Fix:**
```python
# In /auth/signup-with-admin-code — resolve tier dynamically
admin_tier = ADMIN_CODE_TIERS.get(code.lower(), 'insider')
# ... (account creation logic) ...
return {
    "success": True,
    "tier": admin_tier,          # was hardcoded "insider" — now dynamic
    "message": f"Free lifetime {admin_tier.upper()} access activated!",
    ...
}
# Also ensure the DB UPDATE uses admin_tier, not the hardcoded string
```

---

### 🔴 ISSUE #3 — P&L Dollar Precision Inconsistency Across Views

**Location:** Multiple files — three different renderers for the same `pnl` dollar value

**The Issue:**

The same dollar P&L value is formatted three different ways depending on which page or component renders it:

| Renderer | Function Used | Example output for $1,234.50 |
|---|---|---|
| `fundCard()` (homepage) | `fmt$0(v.pnl)` = `Math.round` | `$1,235` |
| `renderFund()` (fund detail) | `fmt$0(v.pnl)` = `Math.round` | `$1,235` |
| `renderMyTracker()` (dashboard tracker) | `Math.abs(v.pnl).toLocaleString()` (no forced decimals) | `$1,234.5` or `$1,234` (locale-dependent) |
| `portfolio-fund.html` stat cards | `fmt$0(pnl)` = `Math.round` | `$1,235` |

`renderMyTracker` (app.js line 1024) uses:
```javascript
sign + '$' + Math.abs(v.pnl).toLocaleString() + ' (' + sign + v.pnl_pct.toFixed(1) + '%)'
```

This produces `$1234.5` or `$1,234.5` depending on the locale, and omits the second decimal place for clean amounts like `$100.50` → `$100.5`. All other renderers consistently use `fmt$0` which rounds to the nearest dollar.

**Impact:** A user who sees `$1,235` on the fund card, then scrolls to the My Tracker section and sees `$1,234.5`, will think the two numbers are different portfolio values. They are the same value rendered inconsistently.

**Recommended Fix:**
```javascript
// app.js renderMyTracker — replace .toLocaleString() with fmt$0
// Line 1024 — BEFORE:
sign + '$' + Math.abs(v.pnl).toLocaleString() + ' (' + sign + v.pnl_pct.toFixed(1) + '%)'

// AFTER:
fmt$0(v.pnl) + ' (' + sign + v.pnl_pct.toFixed(2) + '%)'
// Also fix toFixed(1) → toFixed(2) to match fmtPct used everywhere else
```

---

### 🟡 ISSUE #4 — pnl_pct Precision Inconsistency (1 decimal vs 2 decimals)

**Location:** `app.js line 1024` vs all other percentage renderers

**The Issue:**

`renderMyTracker` renders percentage P&L with `.toFixed(1)` (1 decimal place):
```javascript
// app.js line 1024
v.pnl_pct.toFixed(1) + '%'   // → "+5.3%"
```

Every other percentage renderer in the platform uses `fmtPct()` which calls `.toFixed(2)`:
```javascript
const fmtPct = n => (n>=0?'+':'') + (n||0).toFixed(2) + '%';  // → "+5.34%"
```

This includes: `fundCard()`, `renderFund()`, `portfolio-fund.html stat cards`, `renderStrategyPanel()`, `renderPositions()`, and the Signals panel.

**Impact:** A portfolio showing `+5.34%` on its fund page shows `+5.3%` in the My Tracker panel on the same dashboard — a cosmetic inconsistency that makes users question whether they're looking at the same figure.

**Recommended Fix:**
```javascript
// app.js line 1024 — replace .toFixed(1) with fmtPct()
// BEFORE:
sign + v.pnl_pct.toFixed(1) + '%'
// AFTER:
fmtPct(v.pnl_pct)
```

---

### 🟡 ISSUE #5 — Billing Date Conversion Fragility

**Location:** `dashboard.html line ~1101`

**The Issue:**

```javascript
new Date(billDate * 1000 || billDate).toLocaleDateString(...)
```

This attempts to handle both Unix timestamps (numbers) and ISO date strings with a single expression. The logic depends on `string * 1000` evaluating to `NaN`, and `NaN || billDate` falling through to the raw string.

This works correctly today but is semantically fragile:
- If `billDate` is `0` (falsy), `0 * 1000 = 0`, and `0 || billDate` evaluates to `billDate` (the string) — which would be wrong if `billDate` is genuinely `0`.
- If Stripe ever changes the format of the billing date field, this silent fallback will pass with no error but render garbage.

**Impact:** Currently produces correct output in normal cases. Breaks silently if `billDate = 0` or if a non-ISO string is passed.

**Recommended Fix:**
```javascript
// Explicit type check — no ambiguity
const billDateMs = typeof billDate === 'number' ? billDate * 1000 : Date.parse(billDate);
new Date(billDateMs).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
```

---

### 🟡 ISSUE #6 — Webmaster Referral Discount Logic Inconsistency

**Location:** `Backend/main.py` — `/subscriptions/calculate-price` endpoint (lines 1114-1118)

**The Issue:**

The Webmaster "Build Your Own" pricing endpoint applies a flat `$75.00` referral discount:
```python
# main.py line 1117
discount_amount += 75.00
```

But the standard subscription referral system offers:
- Monthly: **50% off first month** (e.g., $25 off a $49.99/mo plan)
- Annual: **$100 off**

The frontend consistently advertises the referral as "50% off first month or $100 off annual." The Webmaster flow applies neither — it applies a fixed $75 that isn't advertised anywhere in the UI.

**Impact:** A Webmaster user who applies a referral code in the Build Your Own flow gets $75 off, but they were told they'd receive 50% off the first month or $100 off annual. At minimum this is a broken promise. The `/stripe/create-checkout` endpoint (the path the UI actually uses) correctly applies 50%/100% via Stripe coupons — meaning this `/calculate-price` endpoint is inconsistent with what actually happens at checkout, making it unreliable as a price preview.

**Recommended Fix:** Either:
1. Remove the referral logic from `/calculate-price` entirely (since Stripe handles it at checkout), or
2. Align the discount to match the actual checkout behavior: calculate 50% of first month or $100 depending on cycle.

---

### 🟡 ISSUE #7 — `renderRace()` Starting Capital Label vs Actual Capital

**Location:** `app.js line 343` and the data-flow-diagram

**The Issue:**

The data-flow-diagram explicitly lists per-platform starting capitals:
- `wallstbots: $55,000`
- `lvl13: $49,000`
- `bitbot13: $50,000`

All three sites share the same `app.js` codebase. The current fallback `|| 49000` in `renderRace()` is hardcoded to `lvl13.tech`'s value. The wallstbots.tech and bitbot13.tech deployments of the same file would show the wrong starting capital ($49,000) if the tracker API fails, instead of $55,000 and $50,000 respectively.

**Impact:** On tracker outage, wallstbots.tech displays `Starting Capital: $49,000` instead of `$55,000`, and bitbot13.tech displays `$49,000` instead of `$50,000`.

**Recommended Fix:** Each site's `app.js` should declare its own constant at the top of the file, analogous to `PLATFORM`:
```javascript
// wallstbots.tech/assets/app.js
const PLATFORM          = "wallstbots";
const PLATFORM_START_CAP = 55000;

// bitbot13.tech/assets/app.js
const PLATFORM          = "bitbot13";
const PLATFORM_START_CAP = 50000;

// lvl13.tech/assets/app.js
const PLATFORM          = "lvl13";
const PLATFORM_START_CAP = 49000;
```
Then in `renderRace()`:
```javascript
fmt$0((STATE.funds&&STATE.funds.starting_capital) || PLATFORM_START_CAP)
```
And in `fundCard()`:
```javascript
const v = data && data.value ? data.value 
        : { total: PLATFORM_START_CAP, pnl: 0, pnl_pct: 0, day_pnl: 0, day_pct: 0 };
```

---

### ✅ ISSUE #8 — Admin Code UI Banner Incorrect (Minor) — FIXED

**Location:** `app.js line 814` and `line 843/848`

**The Issue:**

When a user enters any admin code, the UI banner hardcodes the displayed tier as "INSIDER":
```javascript
// app.js line 814
msg.innerHTML = '...free lifetime INSIDER access!...'
// app.js line 843
'<p style="color:#ff8c00">🎉 Free Lifetime INSIDER Access</p>'
// app.js line 848
'<button onclick="claimAdminAccess()">Claim Free INSIDER Access</button>'
```

The validate endpoint now correctly returns `tier: "syndicate"` for the `adminm13` code, so the actual account created is correct (aside from Issue #2 in signup). But the UI always announces "INSIDER" regardless of what the backend returned.

**Impact:** Cosmetic — a syndicate-level admin code recipient is told they're getting INSIDER access in the UI even though they'll receive SYNDICATE. The mis-labelling adds confusion, especially when combined with Issue #2 (where the signup actually does create the wrong tier).

**Recommended Fix:**
```javascript
// After applyRefCode() receives the validation response, store the tier:
GY_ADMIN_TIER = data.tier || 'insider';  // "insider" or "syndicate"

// Then reference GY_ADMIN_TIER in the banner/button text:
'Free Lifetime ' + GY_ADMIN_TIER.toUpperCase() + ' Access'
```

---

## PHASE 4 — Confirmed Absolute Alignments ✅

The following equation chains were fully traced from source to display and confirmed to be perfectly aligned:

### ✅ 1. Portfolio Value Chain (the most critical chain)
`refresh_portfolios.py` writes `bot_fund_state` → `main.py /bots/{id}/fund/{fid}/state` returns `total_value` as `float` → `portfolio-fund.html renderFundStats()` reads `fundState.total_value` → displays via `fmt$0(total)`.

Same `fmt$0` used in both `portfolio-fund.html` and `dashboard.html` portfolio cards → **identical display across pages**.

### ✅ 2. Gain/Loss % Chain
`bot_fund_state.gain_loss_pct` (stored as `NUMERIC(10,4)`, rounded to 4 decimal places) → returned as `float` → displayed via `fmtPct()` (`.toFixed(2)+'%'`) consistently on: fund card homepage, fund detail page, portfolio-fund stat card, leaderboard. Same formula everywhere.

### ✅ 3. Subscription Tier → Portfolio Limit (Frontend ↔ Backend)
Both `dashboard.html` and `main.py` use identical if/else chains:
- webmaster → 99, syndicate → 25, insider → 10, member → 5, free → 1.
No divergence. DB writes the correct string tier; frontend reads the string tier; both branch identically.

### ✅ 4. Referral Discount Preview ↔ Actual Stripe Coupon
- Frontend monthly preview: `price × 0.5`
- Stripe coupon created: `percent_off: 50`  → **50% = 0.5 ✓**

- Frontend annual preview: `price − 100`
- Stripe coupon created: `amount_off: 10000` (cents) = $100  → **matches ✓**

### ✅ 5. Holdings Count Cap (Frontend ↔ Backend)
`dashboard.html` warns at 50 holdings. `main.py /bots/{id}/holdings` enforces `cnt >= 50` → `400 error`. Both sides agree the maximum is exactly 50.

### ✅ 6. Referral Credit Amount
UI copy: "$35 bill credit" (app.js line 710, 1253). Backend webhook: `+35` to `referral_credit_balance` (main.py line 1366). **Exact match ✓**

### ✅ 7. Performance Snapshot Rounding Alignment
Backend stores `round(total_value, 2)` and `round(gain_loss_pct, 4)`. Frontend always reads these as floats and renders via `fmt$0` (rounds to integer for display) or `fmtPct` (rounds to 2 decimals for display). No precision loss — the 4-decimal storage of `gain_loss_pct` provides more than enough precision for the 2-decimal display.

### ✅ 8. Portfolio-Fund Capital Calculation
`renderFundStats()` computes `cap = holdings.length × 1000` directly from the live holdings array. The "Started at" label shows this exact computed value. The backend stores `entry_cost` which is also computed as `len(holdings) × 1000` by the refresh script. These are independently computed from the same source (holdings count) and will always agree.

### ✅ 9. Day P&L Calculation
`day_pnl = total_value × (day_pct / 100)` — computed in the backend refresh script, stored in `bot_fund_state`, returned directly to the frontend, displayed via `fmt$0`. No re-derivation on the frontend. Single computation path, no opportunity for divergence.

### ✅ 10. SYNDICATE Upgrade Upsell Copy
"Upgrade to SYNDICATE for just $30/mo more" in `renderThanksAdmin`.  
Math: `SYNDICATE $99.99 − INSIDER $69.99 = $30.00`. **Correct ✓**

---

## Summary — Issue Severity Matrix

| # | Issue | Severity | Affects |
|---|---|---|---|
| 1 | ~~Starting capital fallback mismatch: fundCard=$50k vs renderRace=$49k~~ | ✅ Fixed | lvl13 now $50k across all fallbacks — SpaceX added, 50 stocks total |
| 2 | ~~Admin code signup always returns/activates "insider" tier~~ | ✅ Fixed | Backend now uses `admin_tier` dynamically; frontend stores & displays correct tier |
| 3 | ~~P&L dollar precision: `toLocaleString()` vs `fmt$0`~~ | ✅ Fixed | My Tracker now uses `fmt$0` (total, pnl) and `fmtPct` (pnl_pct, day) — matches all other views |
| 4 | ~~pnl_pct precision: `.toFixed(1)` vs `.toFixed(2)` everywhere else~~ | ✅ Fixed | Resolved as part of Issue #3 — `fmtPct` applied throughout |
| 5 | ~~Billing date: fragile `string * 1000 \|\| string` fallback~~ | ✅ Fixed | Explicit `typeof` check — Unix timestamps × 1000, ISO strings via `Date.parse()` |
| 6 | Webmaster referral: flat $75 discount vs advertised 50%/$100 | 🟡 Medium | Build Your Own flow |
| 7 | Cross-site starting capital: hardcoded 49000 in shared app.js | 🟡 Medium | wallstbots.tech + bitbot13.tech on tracker outage |
| 8 | ~~Admin UI banner hardcodes "INSIDER" regardless of actual tier~~ | ✅ Fixed | All banners, button, and thanks page now use `GY_ADMIN_TIER`; SYNDICATE upsell hidden for syndicate codes |

---

*Report generated: June 12, 2026 — Level XIII Platform Audit*
