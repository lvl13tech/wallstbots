# LEDGER REBUILD ROADMAP — The Permanent Data-Integrity Fix
**Date:** 2026-07-10 · **Status:** APPROVED BY OWNER — this is the standing plan all future sessions execute against.
**Applies to:** wallstbots.tech, aistocks.tech, bitbot13.tech (lvl13.tech untouched per Rule 10; bot13.tech has its own adoption guide).

---

## The Mission (why this exists)

The entire purpose of the platform: **a member sees a trade, copies it at that exact moment, and gets the same result the site shows.** Every architectural decision below serves that sentence. Anything that conflicts with it is wrong by definition.

## The Root Cause Being Eliminated

Today the platform **stores conclusions** — cash, totals, day_open, P&L are written to the database as separate numbers by three cloned engines plus a separate member path. Any two stored numbers can disagree, so the audit keeps catching leaks (vanished cash, day-1 mismatches, impossible member moves). Patching each leak treats symptoms. This roadmap removes the disease: **stop storing conclusions; store only facts and derive everything else.**

## The Target Architecture

### 1. One immutable fill ledger (the single source of truth)
The engine writes exactly ONE kind of record: a **fill** — timestamp (ET), platform, fund/portfolio ID, symbol, side (BUY/SELL), quantity, exact execution price at full storage precision. Once written, never edited, never deleted (except by owner-ordered full reset, which hard-deletes per the standing definition). A fill is exactly what a member copies. The record IS the promise.

### 2. Everything else is derived, never stored
- cash = starting_capital − Σ(buy cost) + Σ(sell proceeds)
- position qty = Σ(buys) − Σ(sells) per symbol
- total = cash + Σ(qty × live price)
- pnl = total − starting_capital (SINCE LAUNCH — this definition stands, per 2026-07-02 decision)
- day_pnl = total − (derived value at prior session close); on day 1, prior close = starting_capital
- per-position P&L% = (live − entry)/entry from the ledger's actual entry prices

These are computed by ONE shared function set at read time (or into a cache that is only ever **recomputed from the ledger**, never hand-adjusted). Vanished cash and drifting day_open become mathematically impossible — those numbers no longer exist independently.

### 3. One engine, three configs
`refresh_wallstbots.py` / `refresh_aistocks.py` / `refresh_bitbot13.py` collapse into ONE engine module. Each platform becomes a config: asset universe, asset class, trading calendar (equity weekday+holiday calendar vs crypto daily). Parity drift in engine logic becomes structurally impossible. This completes step 7 of the recovery order in CLAUDE.md.

### 4. Members are small funds
A member portfolio = the same ledger structure, seeded at its own creation day with N×$1,000. Day-1 Rule falls out naturally: no fills exist before creation, so the portfolio is flat at starting capital until the next trading session's real entries. No separate member math exists to diverge. (Kills the scaling-inheritance class of bugs permanently.)

### 5. Write-time refusal, not read-time detection
Before committing any session's fills, the engine verifies invariants and **refuses to write** on failure (alert instead):
- cash never negative at any point in the day's sequence
- seed day: Σ(cost) + cash == starting capital exactly
- implied one-day move under sanity cap (50%)
- every fill priced from a real quote at fill time, at full precision
- day_pnl == pnl on any fund/portfolio's day 1
Bad numbers never reach the site. The nightly `audit_integrity.py` stays as an independent check, but its expected finding is ZERO.

### Explicitly preserved (do not re-litigate)
- SINCE-LAUNCH Total P&L definition (2026-07-02). The "cost basis / sum-of-holdings" model was wrong — do not reintroduce.
- Day-1 Rule as written in CLAUDE.md Rule 0.
- BOT13 frozen decision-time Edge Score.
- BOT13 session close-out (force-flat at session end).
- lvl13.tech: hands off; only its `/public/tracker/state` reads must keep working.
- 8/6/4 tiered price precision (2026-07-10) — carried into the ledger schema as minimum storage precision.

---

## Build Phases (in order — do not skip ahead)

**Phase 0 — Baseline (before any build).** Fix the 3 open audit failures from 2026-07-10 (wallstbots BOT13 intraday cash drift; aistocks wizard day-1 mismatch; bitbot13 member f74ae1f8 impossible move) OR full-reset them clean. Roadmap work starts from a green audit so shadow comparison is meaningful.

**Phase 1 — Ledger schema + shared engine core (SHADOW ONLY).**
New Supabase table `fills` + new module `Project/scripts/ledger_engine.py` with the derivation functions and write-time invariant guards. Platform configs for all three sites. NOTHING touches live tables, live sites, or existing engines. Deliverable: engine runs in shadow, writing fills to the new table each session.

**Phase 2 — Shadow run + daily comparison.**
Run ledger engine alongside current engines for at least 5 trading sessions. A comparison script diffs derived numbers vs live numbers daily; every diff is explained (either a ledger bug to fix, or a live-engine bug the ledger got right). Exit criteria: 3 consecutive sessions with zero unexplained diffs.

**Phase 3 — Backend reads from the ledger.**
`Backend/main.py` gains derivation endpoints reading the fills table. Frontend data contract (`funds`, `snapshots`, `leaderboards`, `value.total`, `value.pnl_pct`, `positions[]`) is preserved exactly — frontends don't change in this phase (Rule 5). lvl13's tracker endpoint keeps its shape.

**Phase 4 — Cutover on a clean Day 1.**
Owner-ordered FULL RESET (hard-delete, standing definition) of all funds + member portfolios. All three sites cut over to ledger-derived data on the same day. Old engines disabled (not deleted) with a dated .bat. This is the launch baseline: zero legacy numbers to reconcile.

**Phase 5 — Decommission + hardening.**
After 5 clean sessions post-cutover: archive old engines, keep nightly audit as regression tripwire, update ARCHITECTURE.md / REGRESSION_CHECKLIST.md / PROJECT_STATUS.md.

**Every phase ships via a new dated, logged, committed .bat (one-click, timestamped log, no file edits inside the .bat) — per standing rules.**

## Verification the Owner Can Do (each phase)
- Phase 2: open the daily comparison log — it must literally say "0 unexplained differences."
- Phase 3: fund pages look identical before/after backend switch.
- Phase 4: every fund shows exactly N×$1,000, "trading begins next session," and the first trades appear at the next real session open.
- Ongoing: nightly audit email/log says ALL CLEAN.

## Non-Negotiables During the Build
1. No live-site changes until Phase 3, and none without a green shadow comparison.
2. No fix + feature in the same step (Rule 2).
3. Smallest change per step (Rule 1).
4. If ledger and live disagree during shadow, the answer comes from real prices — never "adjust one to match the other."
