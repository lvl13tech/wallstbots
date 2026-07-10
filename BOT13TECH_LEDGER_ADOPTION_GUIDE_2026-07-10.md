# BOT13.TECH — Complete Data-Integrity Adoption Guide (Consolidated)
**Date:** 2026-07-10 (final, consolidated) · **Upload this single file into the bot13.tech project folder.**
This is the one document for bringing bot13.tech to the same data-integrity standard as the
Level 13 platform (wallstbots.tech / aistocks.tech / bitbot13.tech). It contains the target
architecture AND every concrete bug-class fix discovered and applied on 2026-07-10 — apply
them all. Never modify bot13.tech from the WallStBots repo; this document is the handoff.

---

## 1. Mission

A member sees a trade, copies it at that exact moment, and gets the same result the site
shows. Every number displayed must be REAL and VERIFIABLE from real trades. Nothing
fictitious, ever. Data integrity overrides convenience, speed, and cleverness.

## 2. Target Architecture (the permanent fix)

**2.1 Immutable fill ledger — the ONLY thing the engine writes.**
One record type: a fill — timestamp (ET), fund/portfolio ID, symbol, side (BUY/SELL),
quantity, exact execution price at full tier precision. Never edited, never deleted (except
owner-ordered full reset = hard-delete of all history). The fill record is exactly what a
member copies.

**2.2 Derive everything; store no conclusions.**
cash = starting_capital − Σ(buy cost) + Σ(sell proceeds). Position qty = Σbuys − Σsells.
total = cash + Σ(qty × live price). Total P&L = total − starting_capital (SINCE LAUNCH).
Today's Change = total − prior session close (day 1: prior close = starting capital, so
Today's Change == Total P&L by construction). Per-position P&L% = (live − entry)/entry from
actual ledger entries. Cached rollups may only ever be RECOMPUTED from the ledger.

**2.3 The Day-1 Rule.**
Starting capital = (number of assets) × $1,000, nothing else. Nothing trades on the
creation/reset day; first real entries at the NEXT trading session (crypto = next day;
equity = next weekday skipping weekends/US market holidays). Show "trading begins <next
session>". Never inherit prior data, never scale from platform performance.

**2.4 Member portfolios = independent small funds.**
Same ledger structure, seeded at creation with the member's own N×$1,000. Dollars come ONLY
from its own positions. Never scale from platform totals.

**2.5 Write-time refusal.**
Before committing a session, verify and REFUSE TO WRITE on failure (alert, don't publish):
cash never negative at any point in the fill sequence; seed day Σcost + cash == starting
capital exactly; implied one-day move ≤ 50% (crypto) / 30% (equity); day 1 Today's Change ==
Total P&L; every fill priced from a real quote at full tier precision.

**2.6 Independent nightly audit** (separate from the engine) that recomputes every displayed
number and expects ZERO findings. Its job is confirming nothing broke.

## 3. Price Precision (storage tiers — platform standard 2026-07-10)

price < $0.01 → 8 decimals · $0.01–$1 → 6 · $1–$10 → 4 (store 6 where possible) · above → 2–4.
NEVER round a stored entry coarser than its tier: a coarse receipt deletes real P&L%.
Bug this caused: a BUY of 13.3 BILLION SHIB was recorded at price $0.00 (sub-penny rounded
away) — an unpriceable, unverifiable fill. Display may round; STORAGE may not.

## 4. Bug Classes Found & Fixed 2026-07-10 (apply all of these to bot13.tech)

**4.1 BOT13 intraday rotations must BANK realized P&L.**
Symptom: cash went negative by exactly the realized loss of rotated-out losers; the audit
formula cash == day_open − Σcost + Σ(today's SELL realized) failed by −$51.82.
Root cause: each rotation re-deployed the full day_open while realized P&L from exits
vanished. Fix (all engines): keep a running `banked_today` = Σ realized from today's exits
(rotations AND stop-loss re-entries, which close the whole book); persist it in the fund
value across intraday refreshes; total = day_open + banked + Σ open-position P&L; and
AFFORDABILITY-RESIZE any newly added positions so their cost never exceeds
(day_open + banked − kept cost). Never spend money the fund does not have.

**4.2 Rounding remainders are REAL MONEY — never clamp cash to zero.**
Symptom: Σcost 49,978.38 + cash 0.00 ≠ deployed 50,000 (VANISHED CASH, ~$22 deleted).
Root cause: seed wrote cash = max(0, deployed − Σcost) and a restore path only covered funds
missing the deployed_capital record. Fix: cash = deployed_capital − Σcost exactly; the
restore covers ALL funds (reference = recorded deployed_capital when present, else starting
capital, capped at max($50, 0.1% of sc)). If the residual is NEGATIVE the seed overspent —
resize shares, don't clamp.

**4.3 Corrupt member portfolios compound — tight carry-forward guard + hard reset.**
Symptom: a 27-coin/$27,000 member portfolio showed $71,904 (+166%) — two positions "worth"
$35,952 EACH, value == cost, growing every refresh. Fabricated entries (price $0.00 class)
inflated total_value, and the next refresh sized new positions from the inflated total:
a self-compounding ratchet. Fixes: (a) carry-forward sanity guard vs the fund's OWN prior
day-open at 1.5× (was 4× — a 2.66× fabricated jump sailed through; legitimate day moves
never approach 1.5×); (b) when corruption is found, HARD-RESET that member fund to a clean
day-1 (own N×$1,000, positions empty, history deleted, "trading begins next session") — never
try to reconstruct fake history.

**4.4 Audit day-1 detection must be EXACT.**
Symptom: a fund 4 days past reset was flagged as violating the day-1 rule.
Root cause: "prior close == starting capital" was tested with a $30 tolerance, so a real
prior close of $50,027.71 matched the $50,000 baseline. Fix: day-1 detection tolerance =
$0.011 (2dp rounding only). Sanity tolerances and identity tolerances are different things.

**4.5 After a close-out, the positions list is DISPLAY ONLY.**
The feed keeps the day's closed rows visible (with exit info) while pos_val == 0. Anything
deriving state must trust pos_val/holding_cash, not the display list — the fund is all-cash.

**4.6 Guard every file save against mid-write truncation.**
Two files were truncated mid-save on 2026-07-10 alone — one cut a shared engine's tail off
INSIDE a pushed commit (every consumer would have crashed on import at the next scheduled
run). Standing rule: after ANY save of a .py file, run `python -m py_compile` before
committing; deploy scripts must compile-check and hard-abort. Truncation is silent; the
compile check is not.

## 5. Build Order for bot13.tech
1. Baseline: replicate the deep audit (dependency-graph relational checks, not spot checks);
   fix or full-reset anything red FIRST.
2. Apply every §4 fix to the existing engine (they are prerequisites, not optional).
3. Build the fill-ledger schema + engine in SHADOW mode (new tables, zero live changes),
   ingesting the engine's published fills and comparing derived vs displayed daily.
4. Shadow-compare ≥5 sessions; require 3 consecutive sessions with zero unexplained diffs.
5. Backend switches to ledger-derived reads, preserving the frontend data contract exactly.
6. Owner-ordered full reset (hard-delete) → cut over on a clean Day 1 → disable old engine.
7. Keep the nightly audit as a tripwire; expected finding: zero.

## 6. Standing Working Rules
Smallest possible change; one concern per change; never fix + feature in one step. Never
store conclusions; never patch a cached number without fixing the writer. Fix live data
immediately (never "it self-corrects next refresh") AND fix the writer in the same session.
All owner-executed steps ship as one-click, timestamped-logged .bat files (git ops only, no
file edits inside .bats, no API-key prompts). Plain-English summary after every change. If
ledger and live disagree, truth comes from real fill prices — never adjust one number to
match another.
