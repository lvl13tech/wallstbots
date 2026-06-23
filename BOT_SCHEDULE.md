# Bot Operations Timeline

**Last verified:** 2026-06-23, against live code (`bot13_engine.py`, `refresh_wallstbots.py`,
`.github/workflows/refresh-*.yml`) — not from memory or assumption.

There are **5 bots** total, running on **3 different cadences**:

| Bot | Cadence | Sites it runs on |
|---|---|---|
| **BOT13** | Daily (intraday) | wallstbots, aistocks (9:30am–4pm ET) · bitbot13 (9am–9pm ET, 7 days) |
| **Oracle** | Weekly | wallstbots, aistocks, bitbot13 |
| **Wizard** | Monthly | wallstbots, aistocks, bitbot13 |
| **Equalizer** | Static baseline (no recurring trades) | wallstbots, aistocks, bitbot13 |
| **Titan** | Static baseline (no recurring trades) | wallstbots, aistocks, bitbot13 |

---

## Monday–Friday: Daily Actions

### wallstbots.tech & aistocks.tech (equity — BOT13 only trades these hours)

| Time (ET) | Action |
|---|---|
| 9:30 AM | Market opens. BOT13 scores the universe and either opens new positions ("TRADE") or sits in cash/holds, depending on breadth and edge thresholds. If it trades, each new position is logged as a **BUY entry** in BOT13's holdings (positions list) with entry price/time stamped. |
| 9:45 AM | Refresh run — reprices any open BOT13 positions; checks for stop/target triggers. |
| 10:00 AM – 2:45 PM | Refreshes every 15 minutes. BOT13 re-prices held positions, watches for its internal -1.35% stop or +3.0% target on each position, and exits (logs a **SELL entry**) if triggered. |
| 3:30 PM | **Close-out cutoff.** BOT13 force-flattens (sells) any positions still open, so nothing carries overnight. Every position gets a same-day SELL entry in the holdings log. |
| 3:45 PM | Refresh run — confirms flat state, finalizes the day's log. |
| 4:00 PM | Market closes. |
| 4:45 PM | Final end-of-day snapshot taken for the day's record. |

Email behavior: a morning digest goes out around 9:35am ET every weekday regardless of
trading activity. Midday/close-time emails (10am–4:45pm window) only fire if BOT13 actually
bought or sold during that run — no email noise on quiet days.

### bitbot13.tech (crypto — 7 days/week, including weekends)

| Time (ET) | Action |
|---|---|
| 9:00 AM | Crypto session opens. BOT13's crypto engine scores the 50-coin universe on momentum + volume confirmation and opens positions if it finds qualified picks. New positions log a **BUY entry**. |
| 9:00 AM – 9:00 PM | Refreshes every ~15–30 minutes all day. Re-prices held coins, watches for stop/target triggers, logs **SELL entries** on any exit. |
| 9:00 PM | **Close-out cutoff.** Any open crypto positions are force-flattened (SELL logged) so the day closes flat. |
| 9:00 PM – 9:00 AM (overnight) | One quiet reprice run around 1–2am ET to keep data fresh; bot does not open new positions outside its 9am–9pm window. |

This repeats identically every day, Monday through Sunday — bitbot13 is the one bot that
doesn't take weekends off.

---

## Once a Week: Oracle

**Runs on:** wallstbots.tech, aistocks.tech, bitbot13.tech (same logic, each site's own
asset universe)

| When | Action |
|---|---|
| Monday (first refresh of the day) | Oracle recomputes its full portfolio: scores the universe on 5-day + 20-day momentum, RSI, and volume, then picks its top 5 names (capped at 2 per sector) and reallocates capital between them. This replaces last week's picks — old positions are closed out and new ones logged as fresh holdings entries. |
| Tuesday–Friday | Oracle does **not** re-pick. It just gets repriced on every regular refresh run (mark-to-market), same as any held position — no new entries logged unless a position is exited for some other reason. |
| Saturday–Sunday | Oracle shows as holding cash/idle — no active management until the next Monday recompute. |

In short: Oracle makes one decision per week and rides it for five trading days.

---

## Once a Month: Wizard

**Runs on:** wallstbots.tech, aistocks.tech, bitbot13.tech (same logic, each site's own
asset universe)

| When | Action |
|---|---|
| 1st–3rd calendar day of the month (first refresh that lands in that window) | Wizard recomputes its full portfolio: scores the universe on 20-day + 60-day momentum, a Sharpe-ratio proxy, and distance above the 50-day moving average. Picks up to 8 quality names, sector-capped at 3 per sector, sized in quartiles (top names get the biggest allocation). This replaces last month's picks. |
| Rest of the month | Wizard holds. It gets repriced on every regular refresh (mark-to-market) and is flagged (not auto-sold) if any position drops more than 12% from entry — that's a manual review flag, not an automatic exit. |

Wizard makes one decision per month and holds it with patience — it's intentionally the
lowest-turnover bot on the platform.

---

## Not on a Trading Schedule: Equalizer & Titan

These two are **baselines, not active traders.** They are seeded once (on first run / their
inception date) and then simply mark-to-market on every refresh — they do not re-pick,
rebalance, or generate new BUY/SELL entries on a recurring basis:

- **Equalizer** — equal-weight, buy-and-hold across the entire universe. Exists so you can
  see what "just buying everything evenly and holding" would have returned, for comparison
  against the active bots.
- **Titan** — buy-and-hold tilted toward the top 10 names in the universe (overweighted),
  with the remainder equal-weighted. Same purpose: a comparison baseline, not a strategy
  that's meant to trade.

---

## What "logged as a holdings entry" means in practice

Each bot's positions are stored as a `positions[]` list per fund. When a symbol appears
that wasn't there before, that's a BUY entry (with entry price + timestamp stamped).
When a symbol that was held disappears, that's a SELL entry (with exit price, reason, and
realized P&L). BOT13 additionally keeps an explicit append-only trade ledger (`trade_log`)
of every BUY/SELL/resize event, which is what feeds the trade-history view on the dashboard.
Oracle, Wizard, Equalizer, and Titan don't keep that same granular ledger — their "holdings"
are just whatever's currently in their positions list, repriced each run.
