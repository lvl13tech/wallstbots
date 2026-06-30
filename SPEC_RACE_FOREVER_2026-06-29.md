# SPEC — "Race Forever" Engine Fixes (2026-06-29)

**Platform purpose:** all 5 strategies (BOT13, Oracle, Wizard, Equalizer, Titan) race
forever to see which is best over time. Every fund compounds/redeploys its FULL balance
on its cadence. **No fund ever resets toward zero or back to the $50k start.**

Applies to all 3 engines (refresh_wallstbots.py, refresh_aistocks.py, refresh_bitbot13.py)
in parity. bitbot13 differs only by crypto universe + crypto hours.

---

## Cadence (how each fund redeploys its whole balance)

| Fund      | Rebalance cadence              | Compounds full balance? |
|-----------|--------------------------------|-------------------------|
| BOT13     | Intraday (each run) + daily    | YES — already correct   |
| Oracle    | Weekly (Monday)                | FIX — see A             |
| Wizard    | Monthly (1st)                  | FIX — see A             |
| Equalizer | Never rotates (buy & hold)     | YES — mark-to-market    |
| Titan     | Never rotates (buy & hold)     | YES — mark-to-market    |

---

## A. Oracle & Wizard — cumulative P&L + compounding (THE BUG)

**Today:** `total = sc + sum(current positions' pnl)`, and new picks are sized off the
fixed starting `sc` ($50k). So on every rotation the new positions enter at fresh prices →
`sum(pnl)` ≈ 0 → **total snaps back to $50k**, and winnings are never reinvested.
Result seen live: Oracle = exactly $55k / $50k with 0.00% Total P&L despite a positive day.

**Fix:**
1. Track `realized_pnl` on the fund (persisted in state). Starts 0.
2. On a rotation (new picks generated), before replacing positions, compute the CLOSING
   positions' realized gain at current prices and ADD it to `realized_pnl`.
3. `total = sc + realized_pnl + sum(open positions' unrealized pnl)`.
4. `pnl = total - sc` ; `pnl_pct = pnl / sc * 100`  (true cumulative since inception).
5. Size new picks off the CURRENT total (sc + realized_pnl), not fixed sc — so the whole
   balance compounds each rotation. (Pass running capital into run_oracle_decision /
   run_wizard_decision instead of the constant.)

Net effect: Oracle/Wizard behave like BOT13 — balance only goes up/down with real P&L and
carries forward forever; rotations no longer zero the record.

## B. BOT13 — intraday rotation, "trade to win" (TODAY'S COMPLAINT)

**Today:** after the morning pick, the `same_day_trade` guard only RE-PRICES existing
positions. The only intraday exits are a hard stop-loss or the account drawdown kill-switch.
So BOT13 sat on a mild loser all day while better assets ran. No re-evaluation.

**Fix — replace the "re-price only" branch with re-evaluate & rotate:**
On each intraday run (window open, positions held):
1. Re-score the WHOLE universe with the existing composite metric
   (5d 40% / 20d 30% / RSI 20% / volume 10%; 20d-trend gate; sector cap 2; top 5).
2. For each held position, compare its CURRENT composite to the best available non-held
   candidate's composite.
3. **Rotate** (sell laggard, buy candidate) when candidate beats the held score by the
   SWITCH MARGIN (~18% higher composite, "clearly better only" — avoids churn).
4. **Sell to cash** any held position whose OWN composite/edge has turned negative
   (thesis broke), even if no replacement qualifies; redeploy when a real edge returns.
5. Keep existing hard stop-loss + drawdown kill-switch as additional floors.
6. After rotation, re-deploy off the current balance (BOT13 already passes day_open as
   capital, so compounding is preserved).
7. Every sell/buy stamps a real trade_log row (genuine same-day SELL then BUY, SELL first
   on a same-timestamp rotation — consistent with the existing ordering rule).

SWITCH_MARGIN_PCT = 18  (tunable constant). NEG_EDGE_EXIT: composite < 0 → sell to cash.

## C. Never-zero invariant (verify, all 5 funds × 3 engines)

- BOT13: total carries forward (prev_b13_total); never resets to sc except the documented
  bad-data carry-forward guard (>4x/day = bad data). OK.
- Oracle/Wizard: after fix, total = sc + realized_pnl + open unrealized — monotonic w/ real
  P&L, never snaps to sc on rotation. OK after A.
- Equalizer/Titan: persistent positions, mark-to-market, never rotate. OK.

## D. Data-integrity layer (final-reset hardening) — owner-approved 2026-06-29

Starting capital = **$1,000 × universe size**, per platform (NOT a flat number):
- wallstbots = 55 assets -> $55,000 ; aistocks = 50 -> $50,000 ; bitbot13 = 50 -> $50,000.
- FOUND: wallstbots hardcodes 55000, bitbot13 hardcodes 50000; aistocks already uses
  len(UNIVERSE)*1000. FIX: all 3 engines compute `len(UNIVERSE) * 1000` so the baseline
  can never drift from the asset count. All 5 funds on a platform start at this same number.

In-engine guards (bad data never gets written), all 5 funds:
1. **Baseline** = len(UNIVERSE)*1000 (above).
2. **Bad-price guard on ALL funds:** reject zero/null/NaN/negative prices (skip that tick,
   keep prior good value); extend BOT13's >4x/day single-day-multiplication guard to
   Oracle/Wizard/Equalizer/Titan too, so no fund can blow up on a garbage feed.
3. **Per-run reconciliation asserts** (log + flag, never silently pass):
   - total ≈ cash + Σ(shares×price)
   - pnl_pct ≈ (total - sc)/sc*100
   - total ≈ day_open + day_pnl
   On mismatch beyond a small epsilon: print a loud WARNING line (so it shows in the
   Actions log) and do NOT write the bad snapshot.

Standalone tool: **Project/scripts/audit_integrity.py** — run anytime; hits live backend
for all 5 funds × 3 platforms and reports: baseline correct, all-funds-equal-at-start,
reconciliation, pnl_pct, day-change, bad/zero prices, trade-log SELL/BUY pairing, one
snapshot/fund/day, no future/duplicate dates. Prints a clean bill of health or a list of
flags. (Reuses secrets.json key automatically — no key prompt.)

## Sequence
1. Implement A + B + C + D on all 3 engines (parity).
2. py_compile all 3 + NUL check + parity diff (only universe/hours/asset-class differ).
3. Deploy (Backend untouched; engines run in GitHub Actions). One git-only deploy bat.
4. FULL RESET all pages to clean $50k once logic verified — then the race starts fresh
   AND correct.
