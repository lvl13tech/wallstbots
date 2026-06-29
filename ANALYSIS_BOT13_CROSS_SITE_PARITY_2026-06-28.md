# BOT13 Cross-Site Code Parity Analysis — 3 Product Sites

**Date:** 2026-06-28
**Scope:** BOT13 logic across wallstbots.tech, aistocks.tech, bitbot13.tech.
**Method:** Read-only diff of the 3 refresh engines + the 3 frontends.
**Rule of reference:** CLAUDE.md Parity Rule — the 3 product sites must be functionally
identical except: (a) asset universe, (b) per-site branding/JWT, (c) bitbot13's crypto
asset class + crypto trading hours/days. wallstbots is the reference site.

Engines:
- wallstbots → `Project/scripts/refresh_wallstbots.py`  (equity, 9:30a–4p ET, Mon–Fri, close-out 3:30p)
- aistocks   → `Project/scripts/refresh_aistocks.py`     (equity, same hours; AI/Quantum universe)
- bitbot13   → `Project/scripts/refresh_bitbot13.py`     (crypto, 9a–9p ET, 7 days, close-out 9p)

---

## VERDICT

**Frontends: full parity.** `renderTradeLog` / `sortTradeLog` / buy-sell colors /
`traded_today` are byte-identical across all 3 `app.js` (modulo the allowed "Units" vs
"Shares" header) and identical in all 3 `portfolio-fund.html`. No action needed.

**Engines: real drift found — the equity sites are behind bitbot13 and behind each other.**
Two separate problems:

### Problem 1 — This session's BOT13 fixes only landed on bitbot13
Three fixes made while debugging bitbot13 were never propagated to the equity engines:

| Fix | wallstbots | aistocks | bitbot13 |
|-----|:---------:|:--------:|:--------:|
| Carry-forward (HOLD `total = prev_b13_total`) | ✓ | ✓ | ✓ |
| `_display_decision` (show TRADE after close) | ✓ | ✓ | ✓ |
| **Ground-truth guard** (trade_log is authoritative) | ✗ | ✗ | ✓ |
| **`traded_today` derived from trade_log** | ✗ | ✗ | ✓ |
| **Full window/timestamp clamp** (close-out + ledger) | partial | partial | ✓ |

Consequence on wallstbots & aistocks (the bugs we just fixed on crypto still live there):
- A late no-edge re-evaluation can still flip a **traded** day to "held cash / not enough
  edge" (no ground-truth guard, and `traded_today` still keyed off `prev_strategy.picks`
  which a re-eval can wipe).
- Timestamp clamp covers only the close-out branch (count=1), not the trade-log write path,
  so a close-out logged after a dropped cron tick could still stamp a SELL after 4:00 PM.

### Problem 2 — wallstbots vs aistocks drift in the drawdown kill-switch
Even setting aside this session's fixes, the two *equity twins* have diverged:
- **aistocks is MISSING the `and not drawdown_hit` guards** in the `same_day_trade` and
  `close_out_due` conditions that wallstbots has. On a drawdown day the two sites can take
  different paths (aistocks may re-price/close-out when the kill switch should suppress it).
- Different drawdown **rationale text** and `_dd_pct` computation (wallstbots shows the % loss
  and a "Capital protection activated" message; aistocks shows a different message, no %).
- Stop-loss reason string uses `EQUITY_CFG['stop_display']` (wsb) vs `STOP_LOSS_PCT` (aistocks)
  — same value today, but two sources of truth.
- Comment/wording drift.

This is classic clone drift — the exact failure mode CLAUDE.md's Parity Rule exists to prevent.

---

## ALLOWED differences (NOT drift — correct by design)
- **Universe + sector maps:** wallstbots = 55 sector stocks; aistocks = 50 AI/Quantum names;
  bitbot13 = top-50 crypto. Expected.
- **Hours/days/close-out:** EQUITY_CFG (9:30–16:00, Mon–Fri, 3:30 close) vs CRYPTO_CFG
  (9:00–21:00, 7 days, 9:00pm close). Expected.
- **"Units" (bitbot13) vs "Shares" (stocks)** in the trade-history header. Expected.
- **Variable name** `prev_b13_strategy` (equity) vs `b13_prev_strategy` (crypto). Cosmetic;
  harmless, but worth unifying eventually.

---

## RECOMMENDATION
Bring all three engines to parity on the BOT13 logic, using **wallstbots as the reference**
for the drawdown logic and **bitbot13 as the reference** for this session's 3 newer fixes
(ground-truth guard, traded_today-from-log, full timestamp clamp). Net target = every engine
has: carry-forward ✓, `_display_decision` ✓, ground-truth guard ✓, traded_today-from-log ✓,
full window clamp ✓, and the SAME drawdown kill-switch logic + guards.

Apply via bash/Python only (the Edit tool truncates large files in this repo), verify each
with py_compile + NUL check, then deploy all three together (Parity Rule: one change touches
all three). Frontends already match — no frontend changes needed.

Suggested order:
1. Port the 3 newer fixes from bitbot13 → wallstbots + aistocks (adapt CRYPTO→EQUITY cfg,
   crypto→equity var name, 9pm→3:30/4pm).
2. Sync the drawdown kill-switch: make aistocks match wallstbots exactly (add the missing
   `and not drawdown_hit` guards + unified rationale + single stop-display source).
3. Compile + parity-diff all three logic regions until only the allowed differences remain.
4. One deploy for all three; no reset needed (this is logic-only, no data change).
