# BOT13 Page — Data Display Audit: During Trading Hours vs. After Trading Hours

**Date:** 2026-06-23
**Scope:** The BOT13 fund page in BOTH locations, across ALL THREE product sites.
**Purpose:** This is a READ-ONLY audit. Nothing was changed. It documents, box-by-box,
what each part of the page currently shows *during* the trading session vs. *after* the
session closes — so you can mark up each row with what it *should* show, and I'll fix it.

> **How to use this:** For every box below there is a **"During hours shows"**, an
> **"After hours shows"**, and a **"⚠️ Suspected break"** line. Edit the During/After
> lines to match what you actually want. Where I flag a ⚠️, that's where the timestamp /
> Trade History addition most likely broke something. Tell me which ⚠️ items are real and
> I'll correct them on all three sites in one pass.

---

## 0. The two places this page lives (and why they must match)

| # | Where | File | Who sees it | Data source |
|---|-------|------|-------------|-------------|
| 1 | **Public** fund page (e.g. `…/#/fund/bot13`) | `assets/app.js` → `renderFund()` | Anyone | Global tracker: `GET /public/tracker/state` → `funds.bot13.value` |
| 2 | **Members** fund page (`portfolio-fund.html`) | `portfolio-fund.html` inline JS | Logged-in members | Per-member: `GET /bots/{id}/fund/bot13/state` → `fundState` |

Both pages render the **same set of boxes the same way** (the members page is a copy of
the public one, filtered to the member's own coins). So a display rule that's wrong in one
is wrong in both. **This audit applies to both unless a row says otherwise.**

### The three sites are clones — they differ ONLY in trading hours

All three sites run the **same renderer code** and the **same simulation engine**
(`bot13_engine.py`). The only real difference is the session clock:

| Site | Asset class | Session OPEN (ET) | Session CLOSE / close-out (ET) | Trading days |
|------|-------------|-------------------|-------------------------------|--------------|
| wallstbots.tech | Stocks | **9:30 AM** | close-out **3:30 PM**, session ends **4:00 PM** | Mon–Fri |
| aistocks.tech | AI/Quantum stocks | **9:30 AM** | close-out **3:30 PM**, session ends **4:00 PM** | Mon–Fri |
| **bitbot13.tech** | **Crypto** | **9:00 AM** | **close-out AND session end both 9:00 PM** | **All 7 days** |

> ⚠️ **Important nuance for bitbot13:** on the stock sites, close-out (3:30) happens
> *before* the window closes (4:00), so there's a clean "flattened but still in-session"
> moment. On crypto, **close-out and window-close are the same instant (9:00 PM)** — so
> the "End of trading — now holding cash" state and the "outside window" state arrive
> together. Several boxes below behave differently on bitbot13 for exactly this reason.

---

## 1. What the page uses to decide "during" vs. "after"

The page never checks the clock itself. It reads flags the engine writes into the data:

| Flag (in `value` / `fundState`) | Meaning | Set by |
|---|---|---|
| `window_open` | `true` = inside the session right now; `false` = outside session | `window_open(CFG)` in engine |
| `holding_cash` | `true` = BOT13 is in cash, not holding positions | `(decision != "TRADE") or not window_open` |
| `positions[]` | The coins/stocks currently held | enrich step |
| `trade_log[]` | **NEW** — the timestamped BUY/SELL ledger feeding the Trade History box | `stamp_and_log()` **(this is the new code)** |
| `day_open` | Account value at session open (basis for "Today's Change") | carried per session |
| `snapshot_date` | Last day a simulation actually ran (members page only) | snapshot writer |

**The new feature added `trade_log` + `stamp_and_log()` + the `fmtTradeTime()` timestamp
formatter.** Everything that "broke after the timestamp was added" traces to one of these.

---

## 2. Box-by-box audit

### BOX A — "Current Value" stat card

- **During hours shows:** `day_open + sum(position P&L)` — live account value as prices move.
- **After hours shows:** Once BOT13 is flat (close-out), `total` collapses to `day_open`
  (no positions = no live P&L), so the card freezes at the session-close value until the
  next session opens.
- **⚠️ Suspected break:** Low risk. This card reads `value.total`, untouched by the trade
  log. If it looks wrong after hours, it's a *downstream* symptom of Box D/E going empty,
  not this card's own logic.

### BOX B — "Total P&L" stat card (all-time)

- **During hours shows:** `total − starting_capital`, with all-time %.
- **After hours shows:** Same formula; freezes with the value when positions close.
- **⚠️ Suspected break:** Low risk. Independent of the timestamp feature.

### BOX C — "Today's Change" stat card  ← **watch this one**

- **During hours shows:** `total − day_open` and `day_pct` since yesterday — moves live.
- **After hours shows:** On the **stock sites**, after 3:30 close-out BOT13 is flat, so
  `total == day_open` and **Today's Change snaps to $0 / 0.00%** for the rest of the day —
  even though the bot made money intraday. On **bitbot13** the same snap-to-zero happens at
  9:00 PM.
- **⚠️ Suspected break — LIKELY REAL.** Members commonly read this as "the bot gave back
  all its gains after close." The number is technically correct (the bot *is* flat) but it
  **contradicts the Trade History box**, which now shows realized SELL profits for the day.
  Two boxes telling opposite stories is the classic symptom of the new feature. **You need
  to decide:** after close, should "Today's Change" show (a) $0 because flat, or (b) the
  day's *realized* P&L so it matches Trade History? → *Your call here:* ____________

### BOX D — "Strategy" panel ("TODAY'S STRATEGY" / Projected Edge Score / picks)

- **During hours shows:** Today's decision (TRADE / HOLD / CASH), the rationale, the
  Projected Edge Score (BOT13 only), and the pick cards.
- **After hours shows:** Carried forward from the last session (the engine's
  "outside trading window" and "market closed" branches reuse `prev_strategy`), so it keeps
  telling today's story after close.
- **⚠️ Suspected break:** Medium. After close-out the decision flips to `HOLD` but picks
  are preserved — so the panel can say **"HOLD"** while still listing the coins it traded.
  Decide whether that's the intended "here's what it did today" recap or should say
  "Session complete." → *Your call here:* ____________

### BOX E — "Holdings" table  ← **watch this one**

This table has the most states, and it's the one most coupled to the new flags.

- **During hours, in a trade:** One row per held position (Symbol, Units, Entry, Price,
  Value, Today, Total P&L, %).
- **During hours, holding cash:** Single centered row — **"Holding cash"**.
- **After hours (window closed):** Single centered row — **"End of trading — now holding
  cash"** (this exact wording is chosen by `windowOpen === false`).
- **Other after-hours states (members page):** "Awaiting first simulation",
  "Holding Cash — no picks met criteria today", or "has no active positions in your coins
  today."
- **⚠️ Suspected break — LIKELY REAL.** The empty-table message is driven by
  `windowOpen`/`holdingCash`. On **bitbot13**, because window-close and close-out are the
  same instant (9 PM), the table can jump straight from live positions to
  *"End of trading — now holding cash"* with no in-between — and on the stock sites it can
  show "End of trading" from 4 PM even though close-out already flattened at 3:30. If you're
  seeing the **wrong empty-message wording**, or positions vanishing while Trade History
  still lists them, this is the spot. **Decide the desired after-hours Holdings message for
  each case.** → *Your call here:* ____________

### BOX F — "Trade History" table  ← **THE NEW BOX**

- **During hours shows:** Every BUY (and any RESIZE), timestamped via `fmtTradeTime()`
  ("1:05 PM ET"), as the bot enters positions.
- **After hours shows:** The full day's BUYs **plus** the SELLs written at close-out
  (9:00 PM crypto / 3:30 PM stocks), each with realized P&L. This is the only box that
  *gains* detail after hours.
- **⚠️ Suspected break — THIS IS THE NEW CODE.** Specific risks to verify:
  1. **Timestamp display.** `fmtTradeTime()` reads `t.ts` and labels it "ET". But
     `stamp_and_log` stamps `et_now()` on SELLs and **`entry_time` (which may be UTC-ish on
     older rows) on BUYs.** If any BUY `ts` was stored without ET conversion, its time will
     render hours off while still labeled "ET". → verify a known trade's times look right.
  2. **BUY-after-SELL inversion guard.** The engine clamps a SELL's time forward so it's
     never earlier than its BUY. If you ever see a SELL listed *above/earlier* than its BUY,
     the guard isn't catching that lot.
  3. **Box visibility.** The panel is `display:none` until `trade_log` is non-empty. On a
     pure CASH day it stays hidden — confirm that's what you want (vs. "No trades today").
  4. **This box runs for ALL FIVE funds**, not just BOT13 (`stamp_and_log` is called in the
     per-fund loop). For EQUALIZER/TITAN (buy-and-hold baselines) it should essentially
     never log after the initial seed — confirm they aren't generating spurious
     RESIZE/SELL rows from the >2% share-drift rule. **This is the most likely "it broke
     other areas" culprit.** → *Your call here:* ____________

### BOX G — "Signals — Today" (members page only)

- **During hours shows:** Buy/Hold/Sell signal cards filtered to the member's coins.
- **After hours shows:** Same signals (refreshed nightly), unaffected by session state.
- **⚠️ Suspected break:** Low. Reads `STATE.signals`, independent of the trade log. If it's
  empty after hours it's a data-refresh timing issue, not the timestamp feature.

### BOX H — "News — Today" (members page only)

- **During hours / after hours:** Identical — nightly-refreshed headlines filtered to the
  member's coins. No session dependency.
- **⚠️ Suspected break:** None expected from this feature.

### BOX I — "Performance Trajectory" chart

- **During hours shows:** Equity curve from snapshots + today's live point.
- **After hours shows:** Same curve; the final point settles to the close value.
- **⚠️ Suspected break:** Low/indirect — only moves if Box A's `total` is wrong.

### BOX J — "BOT13 Track Record" tile (up/down/cash day tally)

- **During hours / after hours:** Counts up/down/cash days from completed snapshots.
  A day only counts once its snapshot is finalized.
- **⚠️ Suspected break:** Low. Not tied to the trade log. (Historically this tile has had
  its own data issues — out of scope here unless you want it included.)

---

## 3. Quick triage — most-likely-real breaks, in priority order

1. **Box C "Today's Change" snaps to $0 after close** while **Box F "Trade History" shows
   the day's realized profit** → two boxes contradict each other. *(Highest-impact, most
   visible to members.)*
2. **Box F runs for all 5 funds** → EQUALIZER/TITAN baselines may be emitting phantom
   BUY/SELL/RESIZE rows from the 2% share-drift rule. *(Most likely "broke other areas.")*
3. **Box E Holdings after-hours message** wording/timing, especially on bitbot13 where
   close-out == window-close at 9 PM (no clean in-between state).
4. **Box F timestamps** — BUY rows possibly stored in UTC but labeled "ET".
5. **Box D Strategy panel** saying "HOLD" while still showing today's picks after close.

---

## 4. What I need from you

Mark each ⚠️ above as **REAL** (fix it) or **FINE** (intended), and for Boxes C, D, E, F
fill in the *"Your call here"* line with the exact text/number you want shown **during**
vs **after** hours. Per your standing rule, I will treat your description as ground truth —
I won't assert how the site is "supposed" to behave.

Once you've marked it up, I'll apply the corrections to **all three sites at once**
(parity rule), keeping bitbot13's crypto hours, and give you a one-click `.bat` to deploy.

*No code has been changed above. This is documentation only.*

---

# 5. CONFIRMED FIX SPEC (owner-approved 2026-06-23)

> This section is the agreed target behavior. It overrides the "Your call here" blanks
> above. Applies to **all three sites** (parity), keeping bitbot13's crypto hours.

**Unifying principle (owner's words):** After a session ends, **every box freezes on the
last session's final values and holds them until the next session opens** — at which point
it resets. The current bug is the engine flipping boxes into a generic "HOLD / market
closed" look the instant the window closes. That early overwrite is the shared root cause
of the Box C, D, and E breaks.

### Box A — Current Value
No change.

### Box B — Total P&L (all-time)
No change.

### Box C — Today's Change
- **During hours:** live, as today.
- **After hours:** hold the **value at close** (frozen verbatim — the $ and % as they read
  at the final trade / close-out). **Decision: hold value-at-close, NOT $0, NOT recomputed.**
- **At next session open:** reset to $0 / 0.00%, then go live again.
- **Bug:** currently shows a HOLD/zeroed state after hours instead of freezing.

### Box D — Strategy panel
- **During hours:** today's decision + picks, as today.
- **After hours:** **freeze and hold the last session's strategy** (the picks/rationale it
  actually traded) until next open.
- **HOLD status rule:** the panel may show "HOLD" **only on days BOT13 genuinely does not
  trade at all.** It must NOT flip to HOLD just because the window closed after a trading
  day.
- **At next session open:** recompute for the new day.
- **Bug:** currently flips to HOLD after hours on days it DID trade.

### Box E — Holdings table
- **During hours:** show the assets currently purchased/held (as today).
- **After hours:** **still show the assets that were purchased today**, with a final summary
  row:
  - `"End of trading — now holding cash"` if BOT13 traded today, OR
  - `"Holding cash - no trades made today"` if BOT13 made no trades today.
- **At next session open:** reset / repopulate for the new day.
- **Bug:** currently clears/replaces held assets after hours instead of holding them with
  the summary row.

### Box F — Trade History  ← largest change
Purpose: the headline transparency feature — members watch BOT13's buys and sells with
timestamps. BOT13 buys at session open (9:00 AM bitbot13; 9:30 AM wallstbots/aistocks),
the box populates from that first buy, and every subsequent buy/sell across the 15-minute
refreshes appears. It must reconcile with every other box (same assets, same P&L).

1. **Sort — DURING hours:** strict **chronological** order so members can follow the bot
   live.
2. **Sort — AFTER hours:** **alphabetical by symbol, with each symbol's BUY shown first then
   its SELL**, so members can scan "bought X at 9:30, sold X at 3:15" per asset.
3. **Implementation (engineer's call, chosen for permanence):** the engine keeps writing
   `trade_log` as an **immutable, append-only ledger** and never re-orders it. **The page
   sorts a COPY for display**, switching on `window_open` (chronological when open,
   alphabetical buys-then-sells when closed). Rationale: presentation lives in the view, the
   ledger can never be corrupted by a sort, and a missed refresh can't show a stale order
   because sorting runs fresh on every page load. This is the fix that shouldn't need
   revisiting.
4. **Timestamp correctness:** every row's `ts` must be true **ET**. Fix the BUY rows so they
   aren't stored/labeled inconsistently (the current "SELL at 9:30 AM before any BUY" and
   out-of-order rows come from BUYs carrying an older/UTC `entry_time` plus the diff-based
   inference). Going forward, BUYs stamp ET at the moment of entry; SELLs stamp ET at exit;
   the clamp guarantees a SELL is never earlier than its BUY.
5. **No day-before carryover:** BOT13 flattens before close, so a new day must start with no
   leftover positions producing phantom rows. Verify the close-out SELL is logged same-day.
6. **Visibility:** the panel must **NOT** be hidden on a no-trade day. On a pure CASH day it
   shows **"No trades today"** instead of `display:none`.
7. **Freeze after hours:** holds the last session's ledger until next open.
8. **BOT13 ONLY:** **`stamp_and_log` / Trade History must run for BOT13 only — remove it
   from the per-fund loop for oracle, wizard, equalizer, titan.** The baselines were
   generating spurious BUY/SELL/RESIZE rows from the >2% share-drift rule. This is the
   "broke other areas" culprit.
9. **Existing bad history:** **fix logic only** — do not wipe. Correct data repopulates from
   the next session; old rows age out via the 200-entry cap.

### Box G — Signals (members)
No change.

### Box H — News (members)
No change.

### Box I — Performance chart
No change (moves only if Box A changes, which it doesn't).

### Box J — Track Record tile
Out of scope for this fix.

### Parity & delivery
- Apply to **wallstbots.tech, aistocks.tech, bitbot13.tech** in one pass.
- bitbot13 keeps crypto hours (9 AM–9 PM ET, 7 days, close-out == window-close at 9 PM);
  stock sites keep 9:30 AM–4 PM ET, Mon–Fri, close-out 3:30 PM.
- Provide a one-click logged `.bat` to deploy, per standing rules.
- Stabilize first: this is the fix pass; no new features bundled in.

