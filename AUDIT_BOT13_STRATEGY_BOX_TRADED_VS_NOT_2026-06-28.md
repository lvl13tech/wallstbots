# BOT13 Today's Strategy / Holdings / Trade History — Traded vs. Not-Traded Consistency

**Date:** 2026-06-28
**Page:** `…/#/fund/bot13` (public) and the member `portfolio-fund.html`, all 3 sites.
**Purpose:** Define exactly what the three boxes show in each case so they always agree.
The boxes are: **Today's Strategy** (decision + edge score + picks + rationale),
**Holdings** (open positions), **Trade History** (timestamped BUY/SELL ledger).

---

## The two cases

### CASE A — BOT13 TRADED today (edge score exceeded 1.74% at open)

| Box | DURING the session | AFTER close-out (3:30pm stocks / 9:00pm crypto) |
|-----|--------------------|--------------------------------------------------|
| **Today's Strategy** | Decision **TRADE**; **Projected Edge Score = the real morning score (>1.74%)**; the picks it bought; real rationale. | **Unchanged / frozen:** still **TRADE**, still the real edge score, same picks/rationale. **NOT** "HOLD", **NOT** 0%, **no "close-out" message.** |
| **Holdings** | The open positions (symbol, entry, price, value, P&L). | The day's positions shown read-only + final row **"End of trading — now holding cash"**. |
| **Trade History** | A **BUY** row per position as it opens (timestamped, chronological). | The morning BUYs **plus** a matching **SELL** per position at close-out (each SELL with realized P&L). Sorted A–Z by symbol, BUY then SELL. |

**Invariants (must always hold in Case A):**
1. The symbols in **Today's Strategy picks** == the symbols in **Holdings** == the symbols in **Trade History**. No asset appears in one box but not the others.
2. **Every Trade-History asset has exactly one BUY and (by end of day) one SELL of the same share quantity** — BOT13 fully closes every position daily.
3. Edge score is the pre-trade score that *caused* the trade; it never resets to 0 on a day it traded.

### CASE B — BOT13 did NOT trade today (no edge / HOLD)

| Box | DURING the session | AFTER session |
|-----|--------------------|----------------|
| **Today's Strategy** | Decision **HOLD**; **Edge Score 0%** (or the sub-threshold score) with the "insufficient edge" rationale; **no picks**. | Unchanged. |
| **Holdings** | Single row: **"Holding cash - no trades made today"**. | Same. |
| **Trade History** | **"No trades today"** (panel shown, empty-state row). | Same. |

**Invariant (Case B):** all three boxes agree on "nothing happened today" — HOLD, no picks, no holdings, no trade rows.

---

## The bugs found (and the fixes applied this session, all 3 sites)

1. **Edge Score showed 0% even though it traded.**
   *Cause:* the close-out branch hard-set `b13_proj = 0.0`.
   *Fix:* close-out now preserves the morning `projected_return` from the stored strategy.

2. **"HOLD -- daily close-out at 3:30pm ET. All positions flattened" message (nonsense).**
   *Cause:* close-out overwrote the rationale with that string and set decision HOLD.
   *Fix:* rationale is preserved from the morning trade; **display decision stays TRADE**
   when it traded today (HOLD shows only on a true no-trade day). No close-out message.

3. **Trade History showed assets that weren't in Strategy/Holdings, and BUYs without
   matching SELLs.**
   *Cause:* the ledger (`stamp_and_log`) was diffing the **display** positions — which,
   after the after-hours display-freeze, re-showed already-closed holdings — creating
   phantom BUY/SELL rows and breaking pairing.
   *Fix:* the ledger now diffs the **real accounting positions** (`enriched`), tracked in a
   separate `_real_positions` key that the display layer can't pollute. Result: one BUY when
   a real position opens, one matching SELL when it closes (incl. the close-out flatten).

4. **Buy/sell colors wrong.**
   *Fix:* **BUY = blue** always; **SELL = green** if realized profit, **red** if realized loss.
   (Applied in both the public `app.js` and member `portfolio-fund.html` renderers.)

---

## ⚠️ Open decision — existing corrupted Trade-History rows
The phantom rows already written to the live `trade_log` will linger until they age out
(200-row cap). Options:
- **(A) Clear the stored bot13 `trade_log` once** on deploy so the page shows clean,
  correctly-paired data immediately. *(Recommended — the old rows are known-bad.)*
- **(B) Leave them**; correct rows accumulate and bad ones age out over time.

---

## Note on aistocks vs lvl13 naming
The AI/Quantum engine file is still named `refresh_lvl13.py` and prints `[lvl13]` in logs,
but it **is** the aistocks engine (pushes platform `aistocks`). Functionally correct;
cosmetic cleanup (log prefixes, and optionally renaming the file + its workflow reference)
can be done separately on request.
