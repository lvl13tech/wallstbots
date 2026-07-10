# BOT13.TECH — Ledger Architecture Adoption Guide
**Date:** 2026-07-10 · **Purpose:** Upload this file into the bot13.tech project folder so the assistant working on that site can apply the same permanent data-integrity architecture being built for wallstbots.tech / aistocks.tech / bitbot13.tech. **Do not modify bot13.tech from the WallStBots repo — this document is the handoff.**

---

## Mission (identical to the main platform)

A member sees a trade, copies it at that exact moment, and gets the same result the site shows. Every number displayed must be REAL and VERIFIABLE from real trades. Nothing fictitious, ever. Data integrity overrides convenience, speed, and cleverness.

## The Architecture to Adopt

### 1. Immutable fill ledger — the ONLY thing the engine writes
One record type: a **fill** — timestamp (ET), fund/portfolio ID, symbol, side (BUY/SELL), quantity, exact execution price at full precision. Never edited, never deleted (except owner-ordered full reset = hard-delete of all history). The fill record is exactly what a member copies.

**Price storage precision (tiered, already adopted on the main platform 2026-07-10):**
price < $1 → 8 decimals · $1–$10 → 6 decimals minimum (display 4) · above → 4 decimals. Never round a stored entry to fewer decimals than the tier — rounding a receipt deletes real P&L.

### 2. Derive everything; store no conclusions
- cash = starting_capital − Σ(buy cost) + Σ(sell proceeds)
- position qty = Σ(buys) − Σ(sells) per symbol
- total = cash + Σ(qty × live price)
- Total P&L = total − starting_capital (SINCE LAUNCH)
- Today's Change = total − derived value at prior session close (day 1: prior close = starting capital, so Today's Change == Total P&L on day 1 by construction)
- per-position P&L% = (live − entry) / entry using actual ledger entry prices

Do NOT store cash, totals, day_open, or P&L as independent database fields the engine hand-updates. If a cached rollup exists for speed, it must only ever be **recomputed from the ledger**, never adjusted directly.

### 3. The Day-1 Rule (verbatim from the main platform)
- Starting capital = (number of assets) × $1,000. Nothing else.
- Nothing trades on the creation/reset day. The fund/portfolio holds starting capital flat and takes first real entries at the NEXT trading session (crypto = next day; equity = next weekday skipping weekends + US market holidays). Show "trading begins <next session>."
- Never inherit prior data, never scale from platform performance, never reference "yesterday" for something created today.

### 4. Member portfolios = independent small funds
Same ledger structure, seeded at creation day with the member's own N×$1,000. No scaling from platform totals — ever. (The main platform's worst historical bug was member values scaled by platform performance; the ledger design makes this class of bug impossible.)

### 5. Write-time refusal
Before committing a session, verify and REFUSE TO WRITE on failure (alert, don't publish):
- cash never negative at any point in the day's fill sequence
- seed day: Σ(cost) + cash == starting capital exactly
- implied one-day move ≤ 50% sanity cap
- day 1: Today's Change == Total P&L
- every fill priced from a real quote at fill time, full tier precision

### 6. Independent nightly audit
Keep a standalone audit script (separate from the engine) that recomputes every displayed number from the ledger and flags any mismatch. Expected finding: zero. Its job is confirming nothing broke, not catching money leaks.

## Build Order for bot13.tech
1. Baseline: run/replicate the deep audit; fix or full-reset anything red first.
2. Build ledger schema + engine in SHADOW mode (new tables, zero live changes).
3. Shadow-compare against live numbers for ≥5 sessions; require 3 consecutive clean sessions.
4. Backend switches to ledger-derived reads, preserving the existing frontend data contract exactly.
5. Owner-ordered full reset (hard-delete) → cut over on a clean Day 1 → disable old engine.
6. Update the site's architecture docs and regression checklist.

## Standing Working Rules (carry these over)
- Smallest possible change; one concern per change; never fix + feature in one step.
- Never store conclusions; never patch a cached number without fixing the writer.
- All owner-executed steps ship as one-click, timestamped-logged .bat files; no file edits inside .bats; no scripts that prompt for API keys.
- Plain-English summary after every change: what changed, why, what it could affect, how the owner verifies it.
- If ledger and live disagree, truth comes from real prices — never adjust one number to match another.
