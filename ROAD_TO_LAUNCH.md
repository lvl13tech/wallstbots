# WallStBots — Road to Launch (Handoff)

_Owner handoff. Plain-English, execution-ready. Written 2026-07-01._

This document is the runway from "stabilized platform" to "public launch." It captures
where things stand, the five remaining workstreams, how to execute each one safely, the
order to do them in, and the non-negotiable rules that keep the platform set-and-forget.

---

## 0. Where things stand today (baseline)

The platform is **stabilized and every known data bug is fixed at the source and deployed.**
Recent session shipped, all guarded by the deep audit:

- **Day-1 fund math** — Today's Change = Total P&L on day 1 (public + member).
- **Holdings TODAY column** reconciles to the Today's Change box (engines + member).
- **BOT13 member track record** — era-aware; a reset can never show a phantom day (front + back end).
- **News** — moved off rate-limited NewsAPI onto free/unlimited **Google News RSS** (can't blank out).
- **BOT13 Projected Edge Score** — now the frozen/averaged **decision-time** number, shows the
  HOLD reason, never drifts into Today's Change.
- **bitbot13 coin prices** — full crypto precision everywhere (no more $0.00 on sub-dollar coins).

**Truth tool:** `python Project/scripts/audit_integrity.py` — a deep relational audit that checks
every number on every page (public AND member vs public) and prints a clean bill of health or an
exact list of what doesn't reconcile. This is the single source of truth for "are the numbers right."

**Architecture (unchanged):** three product sites — `wallstbots.tech` (55 sector stocks),
`aistocks.tech` (50 AI/quantum), `bitbot13.tech` (50 crypto) — plus the parent marketing site
`lvl13.tech`. All share ONE FastAPI backend + ONE Supabase DB. Five strategies per site
(bot13, oracle, wizard, equalizer, titan). Members run their own scaled copies via
`refresh_portfolios.py`. See `ARCHITECTURE.md` and `PROJECT_STATUS.md`.

---

## 1. Complete data integrity — 14 consecutive clean days

**Goal:** every number on every page stays consistently correct for two straight weeks. That is
the launch gate — no member should ever see a number that doesn't add up.

**How to verify (do this daily):**
1. Run `python Project/scripts/audit_integrity.py`.
2. Green = "RESULT: ALL CLEAN." The only acceptable WARNs are the known, explained ones
   (bot13 banked-realized from rotation; crypto display rounding on the % column; 24/7 carried-
   overnight SELLs). Any **FAILURE** is a real problem — fix it at the source, never with a live
   patch that the next refresh overwrites.
3. Watch the transition days specifically, because that's where edge cases live:
   - **Day 1 → Day 2** after any reset (Today's Change should stop equalling Total P&L on day 2).
   - **Daily close-out** (equities ~3:30/4:00 PM ET; crypto 9:00 PM ET).
   - **Oracle Monday rebalance** and **Wizard month-start rebalance**.
   - **Weekend crypto** (bitbot13 trades; equities don't).

**Recommended (makes it truly set-and-forget):** schedule the audit to run automatically once a
day (a GitHub Action or a cron-job.org hit) and email the result, so you're told when something
drifts instead of having to check. When a member-session token is available, extend the audit to
read member `day_pnl`/`day_pct` history too (today it reconciles member Current Value + Total P&L
vs public, but the member day fields sit behind member auth).

**Done when:** 14 consecutive days of audit PASS across all 3 sites + member portfolios, including
at least one of each transition day above.

---

## 2. Finalize the Reports section

**Current state:** the **frontend renders it** (Sunday Reports list + per-week detail with A–F
grades, week P&L, narrative) and the **backend accepts it** (`data_type: "reports"` is valid), but
there is **no generator and no schedule** — so every site shows "No reports yet." This is the exact
same shape the News section was in before it was fixed, so follow that proven playbook.

**What to build:**
1. `Project/scripts/refresh_reports.py` — per platform, weekly: for each of the 5 funds compute the
   week's P&L %, an **A–F grade**, a short **narrative** ("what worked / what didn't"), and a
   **trade-by-trade review** from the week's trade log. Push per-platform to
   `POST /internal/tracker/push` with `data_type:"reports"` (same auth pattern as news/state).
2. `.github/workflows/refresh-reports.yml` — cron for **Sunday after market close** (e.g. Sun 22:00
   UTC), `workflow_dispatch` enabled, all 3 platforms.
3. Reuse the existing data (state snapshots + trade logs) — no new data source needed, so no rate-
   limit risk.
4. **Reposition for BOT13** (see §3): lead each report with BOT13's week, then the four benchmarks.
5. Add a reports freshness check to `audit_integrity.py` (report exists for the latest completed
   week; grades present for all 5 funds).

**Done when:** reports auto-generate every Sunday, populate all 3 sites, and are BOT13-forward.

---

## 3. Marketing / copy overhaul — make BOT13 the star

**The problem (owner's framing):** the site's copy was written at the very beginning when the pitch
was "watch five strategies race." Since then **BOT13 has proven to be the star** — the disciplined,
edge-gated bot that only trades when it sees a real edge and holds cash otherwise. That is the
reason people will pay to join. The current hero literally reads _"5 strategies. 55 stocks. Watch
them race."_ with a "Sector Stock Tracker" eyebrow — race-first, BOT13 buried as one of five.

**The reposition (narrative spine to carry across the whole site):**
- **Lead with BOT13.** It is the product. The other four (Oracle, Wizard, Equalizer, Titan) become
  the **benchmarks BOT13 is measured against** — proof it earns its edge, not the headline act.
- **Explain the method in one breath:** BOT13 scores the market each day; it only trades when its
  projected edge clears the bar (>1.74%); otherwise it holds cash and risks nothing. _No edge, no
  trade, no loss._ That single idea is the hook — make it unmissable on the home page.
- **Make "why join" concrete:** see BOT13's picks and reasoning live, get its signals by email,
  read the Sunday report card, and (the upsell) **run BOT13 on your own stock list**.
- **One cohesive voice** across hero, How It Works, each fund page, the Reports section, Get Yours,
  and the member emails — today they read like they were written at different times.

**How to execute (low-risk):**
1. Write a **copy deck first** — a page-by-page before/after of every headline, subhead, and body
   block (home, How It Works, fund pages, Get Yours/pricing, emails). Get it approved as a document
   before touching code.
2. Then implement across the 3 product sites. Shared copy stays in **parity** (change all three);
   per-site wording only differs by asset class (stocks / AI & quantum / crypto).
3. Leave `lvl13.tech` alone unless explicitly asked (Rule 10).

**Done when:** a visitor lands, immediately understands what BOT13 does and why it's worth joining,
and the voice is consistent on every page.

---

## 4. Design recommendations

Keep changes surgical (Rule 1) — this is polish, not a rebuild. In priority order:

1. **BOT13 hero spotlight.** Replace the five-across "race strip" as the hero with a single BOT13
   feature card: its live edge score, today's decision (traded / held cash and why), and its track
   record. Move the 5-fund race to a secondary "How BOT13 stacks up" section.
2. **Make the edge score the visual centerpiece** on the BOT13 page — it's the story. Show the
   threshold line (1.74%) visually so "cleared the bar / didn't" is obvious at a glance.
3. **Trust signals up front:** the A–F grades, the track record tile, and the transparency ledger
   (every buy/sell timestamped) — these are what convert skeptics on a trading-sim product.
4. **A clear membership value ladder** on Get Yours: what Free vs Member vs Insider vs Syndicate
   actually unlock, BOT13-framed.
5. **Mobile pass** on the fund tables and hero (the holdings tables are wide).
6. Consistency: number formatting is now correct (crypto decimals shipped); keep one formatting
   convention site-wide.

These are recommendations — pair them with the copy deck (§3) and review before building.

---

## 5. Final pre-launch build: `bot13.tech`

A new, fourth product site — **BOT13 only**, and the most ambitious one. Sequence it **last**,
after §1–§4, because it's the largest build and benefits from the finalized copy/design system.

**Spec (from owner):**
- **BOT13 only** (no Oracle/Wizard/Equalizer/Titan).
- **Universe = any stock on NASDAQ or NYSE** (not a fixed 50/55 list).
- **Starting capital = $10,000.**
- **Current Holdings + Trade History are PRIVATE** — visible only to members of the WallStBots
  platform. Non-members see the bot and its headline performance, but the picks/holdings/trade
  history are gated (teaser + join prompt).
- **Membership: a single $69.99 option**, which **also grants an Insider account on the WallStBots
  platform** (cross-grant).

**Key build decisions & risks to resolve before coding (flagging, not guessing):**
1. **Universe scale.** BOT13 currently scores its whole universe every refresh. NASDAQ+NYSE is
   ~5,000–6,000 tickers — scoring all of them each run is not feasible on the current design or data
   budget. **Recommendation:** add a daily **candidate pre-filter** (a liquid-universe screen — e.g.
   top N by dollar-volume and price above a floor) so BOT13 scores a few hundred quality candidates,
   not the whole exchange. This needs an owner decision on the screen rules.
2. **Price data feed.** Full-exchange coverage needs a data source that can price the candidate set
   reliably (the current yfinance path may need review for breadth/rate limits at this scale).
3. **Cross-platform account link.** "$69.99 grants an Insider account on WallStBots" means the
   bot13.tech checkout must provision/upgrade the same user's tier to `insider` in the shared DB
   (the `insider` tier + Stripe price already exist — this is wiring, not new infrastructure).
4. **Gating.** Holdings + Trade History endpoints must return gated/teaser data to non-members and
   full data only to authenticated WallStBots members.
5. **Reuse, don't reinvent.** Clone the existing site pattern (frontend shell, `auth.js`/`api.js`,
   the shared `bot13_engine.py`, the refresh/deploy machinery) — but single-fund, $10k baseline,
   dynamic universe, gated views, single-tier pricing. Keep it inside the same parity discipline.

**Done when:** bot13.tech is live, BOT13 trades a screened NASDAQ/NYSE universe from $10k, holdings/
trade-history are members-only, and the $69.99 purchase also upgrades the buyer to Insider on
WallStBots.

---

## Suggested sequence & timeline

The two-week data-integrity watch (§1) runs **in parallel** with everything else — it's a
monitoring gate, not a blocking task.

- **Days 1–14 (parallel, always on):** daily audit watch (§1).
- **Week 1:** build the Reports generator + Sunday cron (§2); write and approve the copy deck (§3).
- **Week 2:** implement the copy across the 3 sites (§3) + the priority design changes (§4).
- **After §1–§4 are done and audit is 14-days-clean:** build `bot13.tech` (§5).
- **Launch gate:** 14 clean audit days ✅ + Reports live ✅ + copy cohesive/BOT13-forward ✅ +
  bot13.tech complete ✅.

---

## Non-negotiable rules for whoever executes this

1. **Parity.** A change to any of the three engines (`refresh_wallstbots/aistocks/bitbot13.py`) or
   the shared `bot13_engine.py` MUST be mirrored in the member script `refresh_portfolios.py` in the
   same pass. Public and member must always show identical logic.
2. **Fixes must prevent recurrence.** This is set-and-forget. Fix the root, add a guardrail, and add
   an audit check — never a live patch a refresh will overwrite. If a bug can come back, it isn't fixed.
3. **Deploy via the one-click git `.bat`** run from `C:\Claude\Websites\WallStBots` (never the
   OneDrive copy). Frontends auto-deploy via Cloudflare; `Backend/**` via Cloud Run; engines/scripts
   apply on the next scheduled refresh.
4. **Never touch `lvl13.tech`** unless explicitly told to in that session (Rule 10).
5. **Run the audit before and after** any change; verify long files by actually running them, not
   just compiling (truncation can leave valid-but-incomplete files).

---

_End of handoff._
