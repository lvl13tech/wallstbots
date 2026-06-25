# Member Alert Email Rebuild — Implementation Spec (for sign-off)

**Date:** 2026-06-24
**Goal:** Implement the owner's full email blueprint, all at once, including per-member
trade detection. No code is written until this spec is approved.
**FROM address:** `info@lvl13.tech` (unchanged, per owner). lvl13.tech corporate site untouched.

---

## 1. The six email types (the blueprint)

| # | When | Trigger | Audience scope per email |
|---|------|---------|--------------------------|
| **A. Weekday open** | Mon–Fri, first run after stock open (9:30 ET) | once/day marker | Member BOT13 decisions + signals; BOT13 decisions + signals for WallStBots, Aistocks, BitBot13 |
| **B. Weekend open** | Sat/Sun, first run after crypto open (9:00 ET) | once/day marker | Member BOT13 decisions + signals; BitBot13 decisions + signals; **"Market closed" notice for WallStBots & Aistocks** |
| **C. Intraday trade alert** | Any refresh where BOT13 bought/sold | per-refresh, only if activity | Whatever traded this run: member portfolio and/or any site portfolio. Mon–Fri = all sites; Sat/Sun = member + BitBot13 only |
| **D. Stock close-out** | ~3:30 PM ET (Mon–Fri), when BOT13 flattens stocks | once, on close-out detection | Member portfolio sells + WallStBots sells + Aistocks sells. "Reminder to close stock positions." |
| **E. Crypto close-out** | ~9:00 PM ET (every day), when BOT13 flattens crypto | once, on close-out detection | Member portfolio sells + BitBot13 sells. "Reminder to close crypto positions." |
| **F. (existing) weekly/monthly** | Monday / 1st of month | rolls into A | Adds weekly/monthly recap sections (already supported) |

D and E are deliberately **separate emails at separate times** because stock close (3:30 PM)
and crypto close (9 PM) are different moments — each is its own "close your positions" reminder.

---

## 2. How each trigger is decided (no fragile minute-gates)

All gating moves OUT of the workflow YAML and INTO `send_emails.py`, which is given a
`--kind` argument and self-gates with dated markers so each email type fires exactly once
per ET day and survives dropped cron ticks / backup triggers / re-runs.

```
python send_emails.py --kind open        # A or B (script picks weekday vs weekend by ET day)
python send_emails.py --kind trade        # C  (only sends if NEW trades detected this run)
python send_emails.py --kind close-stock  # D  (only sends once stock close-out is detected)
python send_emails.py --kind close-crypto # E  (only sends once crypto close-out is detected)
```

**Markers** (committed under `Frontends/wallstbots.tech/data/`, one line = ET date):
- `.email_open_sent`         → A/B sent today
- `.email_closestock_sent`   → D sent today
- `.email_closecrypto_sent`  → E sent today
- (C/trade alerts are not date-gated; they're gated on "was there NEW activity this run",
  using the existing prev-state snapshot diff, so each distinct trade event emails once.)

A marker is only written after ≥1 email actually sends, so a provider hiccup retries.

---

## 3. Per-member trade detection (the new plumbing)

Today the email only attaches each member's matching **signals**. The blueprint also needs
each member's **portfolio trade events** ("your portfolio bought X / sold Y").

Feasible because `refresh_portfolios.py` already pulls each member's **`prev_states`** and
computes new `positions` + `trade_log` per member. We add, per member, a BOT13
new-trade diff (same logic as `check_bot13_traded_today.py`, but per member):

1. In `refresh_portfolios.py`, for each member compare new BOT13 `trade_log` buy/sell count
   (and close-out flag) vs `prev_states["bot13"]`. Emit per-member flags:
   `member_traded_today`, `member_closed_out`, and the list of this-run buy/sell rows.
2. Persist those flags into the member's `bot_fund_state` (already upserted to backend), so
   `send_emails.py` can read them per subscriber via `/admin/email-subscribers`
   (we extend that payload with the member's latest BOT13 trade rows + flags).
3. `send_emails.py` then includes a member's portfolio trade lines in C/D/E only when that
   member actually had the activity — each member gets their own correct version.

> If extending the subscriber payload proves heavy, the fallback (same result) is a second
> internal endpoint `/internal/member-bot13-activity` that returns per-member today's BOT13
> trade rows. I'll use whichever is cleaner once I'm in the backend; behavior is identical.

---

## 4. Email content rules (sections shown per type)

- **Member section:** always present (their BOT13 decision, their signals; for C/D/E, their
  portfolio's buy/sell/close rows).
- **Site sections (WallStBots, Aistocks, BitBot13):** BOT13 decision + signals (A/B),
  or buy/sell rows (C), or sell/close rows (D stocks, E crypto).
- **Weekend (B):** WallStBots & Aistocks render a clear **"Market closed — equities resume
  Monday 9:30 AM ET"** notice instead of decisions/signals; BitBot13 shows normally.
- **Data sources:** WallStBots + BitBot13 from their committed `data/` JSON; **Aistocks from
  the backend API** (`/public/tracker/state?platform=aistocks`) — already fixed.

---

## 5. Workflow wiring (which workflow fires what)

| Workflow | Schedule reality | Email calls |
|----------|------------------|-------------|
| refresh-wallstbots.yml | Mon–Fri, stock hours | `--kind open` (every run, self-gates), `--kind trade` (every run, gated on activity), `--kind close-stock` (every run, gated on close-out detection) |
| refresh-lvl13.yml (aistocks) | Mon–Fri, stock hours | none — its trades surface through wallstbots' consolidated sends (aistocks data read from backend) |
| refresh-bitbot13.yml | 7 days, crypto hours | `--kind open` (covers **weekends**, self-gates so it won't double-send on weekdays after wallstbots), `--kind trade` (crypto activity), `--kind close-crypto` (9 PM close-out) |

This gives: weekday open from wallstbots; weekend open from bitbot13; intraday alerts from
whichever market is active; stock close from wallstbots at 3:30; crypto close from bitbot13
at 9 PM. The shared markers prevent any double-send.

---

## 6. Files that will change
- `Project/scripts/send_emails.py` — `--kind` dispatch, the 4 marker types, weekday/weekend
  open logic, close-out emails, per-member trade lines.
- `Project/scripts/email_service.py` — new/adjusted templates: open digest, trade alert,
  stock close-out, crypto close-out, weekend "market closed" notice.
- `Project/scripts/refresh_portfolios.py` — per-member BOT13 new-trade + close-out detection.
- `Backend/main.py` — extend `/admin/email-subscribers` (or add `/internal/member-bot13-activity`)
  with per-member today's BOT13 trade rows/flags. **(Backend change → Cloud Run deploy.)**
- `.github/workflows/refresh-wallstbots.yml` + `refresh-bitbot13.yml` — call the right
  `--kind` steps; commit markers. `refresh-lvl13.yml` — no email step.
- `check_bot13_traded_today.py` — reused/extended for close-out detection (buy/sell vs flatten).

---

## 7. Verify before deploy
- `py_compile` all scripts; `node --check` n/a; YAML parse all workflows.
- Unit-test each marker (no-marker→send, after→skip, new-day→send) and the weekday/weekend
  branch by simulating ET dates.
- Dry-run each `--kind` against current data with a test recipient (FORCE) to eyeball every
  template before going live.
- Backend change goes out via the existing backend deploy; frontend/scripts via a one-click
  logged `.bat`. lvl13 corporate site untouched.

---

## 8. Open schedule confirmations (you mentioned changing the schedule)
1. **Weekday open send time** — currently keyed to ~9:30 ET (13:30 UTC EDT). Keep, or move?
2. **Crypto open send time on weekends** — 9:00 ET (13:00 UTC EDT). Keep?
3. **Stock close-out** at 3:30 PM ET and **crypto close-out** at 9:00 PM ET — these are the
   blueprint's two close emails. Confirm those exact times.

Approve §1–§7 (and answer §8) and I'll build the whole thing, verify, and stage it with a
one-click deploy `.bat` (backend + scripts/workflows), nothing pushed until you run it.
