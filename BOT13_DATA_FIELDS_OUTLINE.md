# BOT13 — Data Box & Field Reference (for the standalone BOT13 site)

Every data box that references **BOT13**, the exact field it reads, and the formula behind it.
Split into **Homepage** and **BOT13 page**. Built from the live frontend + engine code so a new
site can bind to the same data with confidence.

---

## 0. Where the data comes from

One JSON payload feeds everything. Fetch:

```
GET  https://<backend>/public/tracker/state?platform=bitbot13
→ { "data": { ... } }
```

Top-level shape used by BOT13 boxes:

```
data.starting_capital            number   e.g. 50000  (= number of coins × $1,000)
data.funds.bot13                 object   the BOT13 fund (below)
data.funds.bot13.value           object   all the numbers (below)
data.funds.bot13.current_strategy object  today's decision / edge score / picks (below)
data.snapshots                   array    daily history: [{date, bot13, oracle, wizard, ...}, ...]
```

Two more feeds power the homepage's non-fund BOT13 context (optional for a bot13-only site):

```
GET /public/tracker/signals?platform=bitbot13   → per-coin Buy/Sell/Hold signals
GET /public/tracker/news?platform=bitbot13      → filtered crypto news
```

---

## 1. HOMEPAGE — every box that references BOT13

### 1A. BOT13 Track Record tile  *(the flagship BOT13 box)*
Computed 100% from `data.snapshots` (day-over-day BOT13 deltas). No extra endpoint.

| Stat shown | How it's computed |
|---|---|
| **Up days** | count of days where `bot13` rose > **+0.05%** vs the prior day's `bot13` |
| **Down days** | count of days where `bot13` fell < **−0.05%** vs prior day |
| **Cash days** | count of days where the move was between −0.05% and +0.05% (flat/no-edge) |
| **Best day** | max single-day % change: `max( bot13[d]/bot13[d-1] − 1 ) × 100` |
| **Worst day** | min single-day % change (same formula, minimum) |

Rules: needs ≥ 2 snapshots or it shows a "Fresh start" state. Down-day count must equal the number
of negative daily deltas (audited).

### 1B. Live Leaderboard — Today (strip)
One row per fund; the BOT13 row reads:

| Field on page | Source | Formula |
|---|---|---|
| Name / kind | static ("BOT13" / "Daily intraday bot") | — |
| Today % | `funds.bot13.value.day_pct` | `day_pnl ÷ day_open × 100` (color by `day_pnl` sign) |

### 1C. The Race — BOT13 fund card
| Box on card | Source | Formula |
|---|---|---|
| Current value | `funds.bot13.value.total` | `cash + pos_val` |
| P&L $ ("since inception") | `funds.bot13.value.pnl` | `total − starting_capital` |
| P&L % | `funds.bot13.value.pnl_pct` | `pnl ÷ starting_capital × 100` |
| Today % | `funds.bot13.value.day_pct` | `day_pnl ÷ day_open × 100` |

### 1D. Performance Trajectory chart
BOT13 line = each snapshot's `snapshots[i].bot13` (the fund's **total / Current Value** at that day's
close) plotted over time.

### 1E. Hero copy (context, not a data box)
`data.starting_capital` (e.g. "$50,000 starting capital") and coin count
(`signals.universe_size`, default 50).

> Note: the parent site (lvl13.tech) also shows a **BOT13 P&L** figure read from this same
> `GET /public/tracker/state?platform=bitbot13` → `funds.bot13.value.pnl` / `pnl_pct`.

---

## 2. BOT13 PAGE — every box (route `#/fund/bot13`)

### 2A. Header — 3 stat cards
| Box | Source | Formula |
|---|---|---|
| **Current Value** | `value.total` | `cash + pos_val` |
| — sublabel "Started at $X" | `data.starting_capital` (or `fund.starting_capital`) | `= number of coins × $1,000` |
| **Total P&L $** | `value.pnl` | `total − starting_capital` (since launch) |
| **Total P&L %** | `value.pnl_pct` | `pnl ÷ starting_capital × 100` |
| **Today's Change $** | `value.day_pnl` | `total − day_open` |
| **Today's Change %** | `value.day_pct` | `day_pnl ÷ day_open × 100` |
| (baseline) | `value.day_open` | the value BOT13 started today at = prior day's close (= starting capital on day 1) |

### 2B. Current Session's Strategy panel  *(`current_strategy`)*
| Element | Source | Notes |
|---|---|---|
| Panel label | static "CURRENT SESSION'S STRATEGY" | BOT13 is daily |
| Period | `current_strategy.day` | "Day of YYYY-MM-DD" |
| Decision | `current_strategy.decision` | `TRADE` \| `HOLD` \| `CASH`. If it traded then closed out, show "TRADED — closed for the day" |
| **Projected Edge Score** | `current_strategy.projected_return` | the FROZEN pre-trade edge score for the day (a %), **not** the live return. Must exceed the trade threshold (**1.74%**) to trade. Never equals Today's Change. |
| Rationale | `current_strategy.rationale` | plain-English reason (leading "Projected return:" prefix is stripped for display) |
| Picks (grid) | `current_strategy.picks[]` | each pick below |
| `traded_today` | `current_strategy.traded_today` | keeps picks visible after close-out instead of a "100% CASH" card |

Each **pick** (`current_strategy.picks[i]`):

```
symbol       string   coin ticker
weight       number   0..1  → shown as "Wt NN%"
score        number   the pick's edge score (shown +/-)
rationale    string   why it was picked
indicators   object   any of: mom_1d, mom_5d, mom_20d, mom_60d (momentum %), rsi_14, macd_pct
```

On a true no-trade day (`decision` = CASH/HOLD and not traded_today) the panel shows a single
**"100% CASH — No positions — holding cash"** card instead of picks.

### 2C. Current Holdings table  *(`value.positions[]`)*
Columns and the field each reads:

| Column | Field | Formula |
|---|---|---|
| Symbol | `positions[i].symbol` | — |
| Units | `positions[i].shares` | coins held |
| Entry | `positions[i].entry_price` | real price paid per coin at buy |
| Price | `positions[i].price` | current price |
| Value | `positions[i].value` | `shares × price` |
| Today | `positions[i].day_pct` / `day_pnl` | `shares × (price − prior close)`; % vs prior close. If bought today, Today = its Total P&L |
| Total P&L | `positions[i].pnl` | `value − cost_basis`  (cost_basis = `shares × entry_price`) |
| % | `positions[i].pnl_pct` | `(price ÷ entry_price − 1) × 100` |

Cash-state rows (no table data):
- Session over → "End of trading session - holding cash" (if it traded today) else "Holding cash - no edge".
- Session open but flat → "Holding cash - no edge".
Driven by `value.window_open` (false = session over), `value.holding_cash` (true = flat), `value.traded_today`.

### 2D. Trade History — "Box F"  *(BOT13-ONLY, `value.trade_log[]`)*
| Column | Field | Notes |
|---|---|---|
| Time | `trade_log[i].ts` | shown as "h:mm AM/PM ET" |
| Action | `trade_log[i].action` | `BUY` (blue) or `SELL` (green if profit, red if loss) |
| Symbol | `trade_log[i].symbol` | coin |
| Units | `trade_log[i].shares` | coins traded |
| Price | `trade_log[i].price` | execution price |
| Realized P&L | `trade_log[i].realized` | only on SELL rows: `(exit − entry) × shares` |
| Note | `trade_log[i].reason` | e.g. "daily close-out", "rotation", stop, etc. |

Sort: during the session → chronological (SELL before BUY at the same timestamp — closes free capital
first); after close → grouped as BUY→SELL pairs ordered by each symbol's first buy time. Empty day
shows "No trades today" (never hidden for BOT13). Header shows today's ET date.

### 2E. BOT13 Track Record tile (repeated)
Same tile as **1A**, also rendered at the bottom of the BOT13 page.

---

## 3. Full BOT13 data dictionary (bind against these)

`data.funds.bot13.value`:

```
total          number   Current Value = cash + pos_val
cash           number   uninvested cash
pos_val        number   market value of holdings = Σ(shares × price)
pnl            number   Total P&L (since launch) = total − starting_capital
pnl_pct        number   pnl ÷ starting_capital × 100
day_pnl        number   Today's Change = total − day_open
day_pct        number   day_pnl ÷ day_open × 100
day_open       number   value BOT13 started today at (prior day's close; = sc on day 1)
day_open_date  string   the date day_open belongs to (YYYY-MM-DD)
holding_cash   bool     true → flat, pos_val == 0, cash == total
window_open    bool     true → trading session is open; false → session ended (show cash state)
traded_today   bool     BOT13 executed at least one trade today
positions[]    array    { symbol, shares, entry_price, price, value, cost_basis, pnl, pnl_pct, day_pnl, day_pct }
trade_log[]    array    { ts, action(BUY|SELL), symbol, shares, price, realized, reason }
```

`data.funds.bot13.current_strategy`:

```
day               string   "YYYY-MM-DD"
decision          string   TRADE | HOLD | CASH
projected_return  number   FROZEN daily Edge Score (%), must exceed 1.74% to trade
rationale         string
traded_today      bool
picks[]           array    { symbol, weight(0..1), score, rationale, indicators{mom_1d,mom_5d,mom_20d,mom_60d,rsi_14,macd_pct} }
proj_samples      number   (internal) how many decision samples fed the frozen score
proj_last_set     string   (internal) when the score was frozen
session_ended     bool     (internal) session-close flag
```

`data.snapshots[i]`: `{ date:"YYYY-MM-DD", bot13:<total>, oracle:<total>, wizard:<total>, equalizer:<total>, titan:<total> }`
— BOT13 track record + trajectory chart are computed from the `bot13` series.

---

## 4. BOT13 behaviour rules the numbers must obey (for the audit on the new site)

- **Daily bot:** buys at session open, sells everything before session close; after close it is in **cash**
  (`pos_val == 0`, `cash == total`, `holding_cash == true`).
- **Only trades on an edge:** if the day's Projected Edge Score ≤ 1.74%, it holds cash — no trade, no risk.
- **Total P&L = since launch** = `total − starting_capital`; **Today's Change = today only** = `total − day_open`.
- **Day 1:** Today's Change equals Total P&L (both measured from starting capital).
- **Fresh fund:** on inception day it deploys exactly the starting capital, so `Σ(cost_basis) == starting_capital`
  (guards against a reset "holdover").
- **Edge Score** is the frozen decision-time number for the day — it must never equal Today's Change.
- Every SELL in Trade History carries a `realized` P&L; every traded coin shows a BUY and a matching SELL by end of day.
- `starting_capital = number of coins × $1,000` (bitbot13 = 50 coins → $50,000).
