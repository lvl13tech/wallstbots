# Member Alert Emails — How They Work, Why They Stopped, and the Correct Sequence

**Date:** 2026-06-24
**Scope:** The daily/weekly/monthly member alert emails for all three sites.
**Status:** Read-only investigation. No code changed. One diagnostic `.bat` provided.

---

## 1. The sequence, end to end (how it's SUPPOSED to work)

Emails are **not** sent by the websites or the backend. They are sent by a Python
script that runs **inside the GitHub Actions refresh workflows**, using **Resend**
(the email provider). One consolidated email per member covers all three sites.

GitHub Actions cron fires (refresh-wallstbots.yml / refresh-lvl13.yml / refresh-bitbot13.yml)
        │
        ▼
[1] Refresh step runs refresh_<platform>.py
        → recomputes bot P&L, writes Frontends/<site>/data/state.json + signals.json
        → commits & pushes the updated JSON
        │
        ▼
[2] "Snapshot prior trade count" step saved /tmp/prev_state.json BEFORE the refresh
        (used to detect a NEW trade this run)
        │
        ▼
[3] Email dispatch step decides WHETHER to send:
        • Manual run (workflow_dispatch)            → always send (FORCE_SEND=true)
        • Morning window (HOUR/MIN gate, see §4)     → always send the daily digest
        • Any other intraday run                     → send ONLY if check_bot13_traded_today.py
                                                       prints "YES" (a new BUY/SELL happened
                                                       this run) — the "trading began" alert
        │
        ▼
[4] python send_emails.py  [--weekly] [--monthly]
        a. Loads state.json + signals.json for wallstbots, bitbot13, lvl13
        b. Staleness check: if a platform's data date != today (ET), that platform's
           SECTION is suppressed (unless FORCE_SEND). Whole email still sends.
        c. get_subscribers() → GET {BACKEND_URL}/admin/email-subscribers
           (needs BACKEND_URL + INTERNAL_API_KEY)
        d. For each subscriber: attach the signals that match their holdings per platform
        e. Split into daily / weekly / monthly recipient lists by their email prefs
        f. build_consolidated_email(...) → one HTML email per recipient
        │
        ▼
[5] email_service.send_batch() → send_email() → POST https://api.resend.com/emails
        FROM = "Wall St. Bots <info@lvl13.tech>"
        • 200/201 → counted as "sent"
        • anything else → printed as FAILED and counted as "failed" (NO crash, NO retry)

**Key files**

| File | Role |
|------|------|
| `.github/workflows/refresh-wallstbots.yml` | Cron + the email dispatch gate (morning + trade-alert) |
| `.github/workflows/refresh-lvl13.yml` | Same, for the **aistocks** engine (lvl13 = its filename only) |
| `.github/workflows/refresh-bitbot13.yml` | Same, for crypto |
| `Project/scripts/send_emails.py` | Orchestrates: load data, fetch subscribers, build, send |
| `Project/scripts/email_service.py` | Resend sender + all the HTML templates. `FROM_EMAIL` lives here |
| `Project/scripts/check_bot13_traded_today.py` | Prints YES/NO — the intraday "did BOT13 trade?" gate |
| Backend `GET /admin/email-subscribers` | Returns the opted-in member list + per-platform holdings + prefs |

---

## 2. Most likely reasons emails stopped (ranked)

Everything below fails **silently** — the workflow still goes green, so "it looks like
it ran" but nothing arrives. Ranked by fit to "stopped a few days ago after recent changes."

### 🥇 #1 — Resend is rejecting every send (FROM domain `lvl13.tech`)
`email_service.py` sends as **`info@lvl13.tech`**. Resend only delivers from a
**verified domain**. lvl13.tech was just rebuilt as the corporate site — if that
migration changed the domain's DNS (SPF/DKIM/MX/verification records), Resend now
returns a non-200 ("domain not verified" / "from address not allowed"), `send_email`
prints FAILED and returns False, and **zero emails go out** while the workflow stays
green. This fits the timeline (migration → DNS change → emails stop) better than
anything else. **Check first.**

### 🥈 #2 — The morning send gate / cron isn't firing
The morning "always send" depends on a single narrow time match (see §4) AND on
GitHub's cron actually firing that exact run. GitHub cron is best-effort/no-SLA
(you already added cron-job.org as backup for the refresh). If the one 13:30-UTC run
is the dropped one, and BOT13 didn't trade intraday, **no email that day**. Several
missed days in a row is plausible if the morning slot keeps getting skipped.

### 🥉 #3 — Subscriber fetch returns empty
If `BACKEND_URL` or `INTERNAL_API_KEY` changed, or `/admin/email-subscribers` errors,
`get_subscribers()` returns `[]` and the script prints "No subscribers — done." and
exits. Sends nothing, exits 0 (green).

### #4 — The lvl13 data path is broken (confirmed, but NOT the zero-email cause)
`send_emails.py` still loads `Frontends/lvl13.tech/data/state.json`, which **no longer
exists** (that data is now under aistocks). Confirmed locally: the load fails and the
"Level XIII" section is silently dropped. The email **still builds and sends** (verified
locally, 24 KB HTML), so this is a real bug to fix but not why everything stopped.

---

## 3. What I verified locally (read-only)
- `email_service.py` and `send_emails.py` import cleanly; all functions present.
- `build_consolidated_email(...)` builds a full 24 KB email even with the broken lvl13
  data — so a bad lvl13 path does **not** crash the send.
- `Frontends/lvl13.tech/data/state.json` is **missing** (load fails, section suppressed).
- wallstbots data parses fresh; bitbot13 reads "stale" only because it was past midnight
  UTC at check time (normal).
- I could **not** see the live Resend response or the GitHub run logs from here — that's
  what the diagnostic `.bat` is for.

---

## 4. The timing gate (worth confirming as "correct going forward")
Morning "always send" conditions actually in the workflows today:

| Workflow | Morning gate | Cron that should hit it |
|----------|-------------|--------------------------|
| refresh-wallstbots.yml | `HOUR=13 AND MIN<45` (UTC) | `30,45 13 * * 1-5` → only the **13:30** run passes (13:45 fails `<45`) |
| refresh-lvl13.yml (aistocks) | `HOUR=13 AND MIN<45` | same — only 13:30 passes |
| refresh-bitbot13.yml | `HOUR=14 AND MIN<45` | `*/15 13-23` → **14:00, 14:15, 14:30 all pass** |

Two correctness problems to decide on:
1. **All three workflows call the same consolidated `send_emails.py`.** On a normal
   morning that's potentially **multiple identical emails** to each member (one per
   workflow whose gate passes — and bitbot13's gate passes 3× at 14:00/14:15/14:30).
   The file header even says it should be "called only from refresh-wallstbots.yml."
   → Recommendation: send the consolidated daily email from **exactly one** workflow,
   once, and remove the dispatch step from the other two (they keep their own
   intraday "BOT13 traded" alerts only if you want those).
2. **The morning gate hinges on one fragile cron slot.** → Recommendation: widen the
   gate (e.g. fire on the first run at/after 13:30 UTC and set a "sent today" guard) or
   trigger the daily send from the cron-job.org backup too, so a single dropped GitHub
   cron run can't kill the day's email.

---

## 5. The correct go-forward sequence (target)
1. **One** workflow owns the **daily consolidated** send, fired once in the morning,
   with a guard so it can't double-send.
2. Intraday "BOT13 traded" alerts (optional) fire from each platform's workflow only on
   a genuine new BUY/SELL (`check_bot13_traded_today.py` = YES), deduped so a member
   gets one alert per real event, not one per workflow.
3. `FROM_EMAIL` uses a **verified** Resend domain. If lvl13.tech is staying corporate,
   verify it in Resend (re-add SPF/DKIM) OR switch the from-address to a domain that is
   verified (e.g. an aistocks/wallstbots domain you control).
4. `send_emails.py` loads **aistocks** data, not the dead `lvl13.tech/data` path.
5. Staleness check uses ET consistently (it does now via `_et_today()`), so weekend/old
   data is suppressed per-section without blocking the whole email.
6. Every send failure is **visible** — surface Resend's error in the workflow log (it
   already prints it) and consider failing the workflow step on a 100%-failed batch so a
   silent outage like this can't run for days unnoticed.

---

## 6. Next step — run the diagnostic
Double-click **`DIAGNOSE-emails_2026-06-24.bat`** (set `TEST_TO` to your email first).
It is read-only except for **one** test email to you. It will capture, into
`DIAGNOSE-emails_LOG.txt`:
- the recent git history of the email code + all 3 workflows (pins exactly what changed),
- whether the secrets are present locally,
- the **real Resend API response** to a live test send — which will say outright whether
  Resend is rejecting `info@lvl13.tech` (confirms suspect #1) or accepting it (which
  points the finger at the workflow gate/cron, suspect #2).

Send me `DIAGNOSE-emails_LOG.txt` and I'll pinpoint the exact fix and ship it to all the
right files in one pass (parity-safe; lvl13 corporate site untouched).

---

## 7. CONFIRMED ROOT CAUSE + FIX IMPLEMENTED (2026-06-24, NOT YET DEPLOYED)

**Confirmed cause of the outage:** a manual (workflow_dispatch) run sent successfully —
so Resend, the domain, secrets, and subscribers are all fine. The outage was that
`send_emails.py` was **never invoked on scheduled runs**: the morning send was gated on
`HOUR=13 && MIN<45` (UTC), which only the single **13:30 UTC** cron tick satisfies. When
GitHub drops that one tick (best-effort scheduler), nothing sends — and the cron-job.org
backup didn't help because the workflow it triggers **re-checks the same minute-gate** and
falls through. Not a delivery problem; a trigger-gate problem.

**Fix implemented (code only — review the doc / adjust schedule before deploying):**
1. **Send-once-per-day marker** in `send_emails.py`. The daily email now sends on the
   FIRST run of the ET day and writes `Frontends/wallstbots.tech/data/.last_daily_email`;
   later runs (any trigger, including backups/re-runs) see the marker and skip. Immune to
   dropped cron ticks and double-sends. The marker is only written if ≥1 email actually
   sent, so a provider outage retries next run instead of being marked done. `--force`
   (and manual workflow_dispatch) bypasses the marker for testing. Verified locally:
   no-marker→send, after→skip, new-day→send.
2. **AI/quantum section fixed.** `send_emails.py` now fetches the aistocks section from the
   backend API (`/public/tracker/state?platform=aistocks`) instead of the dead
   `Frontends/lvl13.tech/data` path. (The leftover `aistocks.tech/data/*` files are orphaned
   — site reads the backend.)
3. **One owner for the daily email.** Only `refresh-wallstbots.yml` calls `send_emails.py`
   now (every run; the script gates to once/day) + commits the marker. The daily-send step
   was REMOVED from `refresh-lvl13.yml` and `refresh-bitbot13.yml` to stop duplicate emails.
   The old fragile HOUR/MIN gate is gone.

**⚠️ OPEN ITEM for your schedule review — weekend crypto emails.**
wallstbots runs **Mon–Fri only**, so as written, **no daily email goes out Sat/Sun** even
though bitbot13 (crypto) trades 7 days. If you want weekend emails, the clean fix is to let
`refresh-bitbot13.yml` also call `send_emails.py` (it's marker-gated, so it only sends on
days wallstbots didn't — i.e. weekends) and commit the marker. I left this OUT pending your
decision, and noted it inline in `refresh-bitbot13.yml`. Tell me your preferred email
schedule and I'll finalize this piece before deploying.

**Files changed (not yet committed/pushed):**
`Project/scripts/send_emails.py`, `.github/workflows/refresh-wallstbots.yml`,
`.github/workflows/refresh-lvl13.yml`, `.github/workflows/refresh-bitbot13.yml`.
Verified: send_emails.py `py_compile` clean; all 3 workflows parse as valid YAML; marker
logic unit-tested. **No deploy yet — awaiting your schedule decision.**
