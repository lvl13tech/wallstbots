# Verified Punch List — 2026-06-22

**What this is:** You said it feels like a lot of past fixes either didn't deploy or got
cut off. I checked that directly — not by re-reading old status notes and trusting them,
but by reading the actual code in the repo AND pulling the actual live pages from
wallstbots.tech, aistocks.tech, and bitbot13.tech and the live backend, and comparing all
three (doc claim → repo code → live page) line by line.

**Bottom line up front:** Your instinct was right in one specific spot (see #1 below), but
it's not the widespread problem it feels like. Every other major feature from the last two
weeks of session notes — the trade ledger, the BOT13 Track Record tile, the 15-minute
refresh, the Stripe/Manage Subscription fix, free signup, the timestamp fix — is genuinely
live on all 3 sites right now, today, verified by pulling the real pages.

---

## 1. 🟡 OPEN — parked per your call, NOT a simple fix

**aistocks.tech shows "$49,000" as the "Started at" number on the bot race display.**
- Where: `Frontends/aistocks.tech/assets/app.js`, line 557.
- Your correction (2026-06-22): this isn't a hardcode bug — aistocks truly did start at
  $49,000, but a stock was added to the universe later, which complicates what the
  "correct" number actually is now. Not a one-line fix.
- Your call: leave it open for now. May ultimately need a **full reset** (hard-delete all
  5 aistocks bots' history at the source) rather than a code patch.
- Status: parked. No fix will be made without further direction from you.

---

## 2. ✅ VERIFIED LIVE — these are genuinely done, on all 3 sites, right now

Checked by pulling the actual live HTML/JS from each site (not just the repo):

- **BOT13 Track Record tile** — homepage, bot13's own page, AND the members-area portfolio
  page. All 3 sites confirmed live.
- **Trade ledger / Trade History panel** — every buy/sell timestamped and shown to members,
  "Bought" column on holdings. All 3 sites confirmed live.
- **15-minute refresh during trading hours + anti-spam emails** (only emails on an actual
  trade, not every refresh). Confirmed in the live GitHub Actions schedule.
- **Bad-data guards** (rejects garbage price spikes instead of trading on them) — confirmed
  in the shared engine all bots use.
- **"Manage Subscription" button / Stripe billing portal** — confirmed live on all 3
  dashboards.
- **Free signup path** (`/auth/signup-free`) — confirmed reachable on the live backend AND
  wired up on all 3 sites' frontend.
- **Timestamp display fix** ("-226m ago" bug) — confirmed identical fix live on all 3.
- **Backend is live and current** — health check OK, and the newer endpoints (snapshot
  wipe, free signup, promo code validation) are all reachable on the live backend, not 404.
- **No file-truncation found anywhere right now** — swept every HTML file across all 3
  sites; all end correctly. The pre-commit guard that blocks this is installed and does
  check Python files too (confirmed by reading the actual hook script), not just HTML.

---

## 3. 📝 Documentation error (no live impact, just a confusing note)

`PROJECT_STATUS.md`'s 2026-06-15 entry says **aistocks** was missing the
"Manage Subscription" button fix. The actual commit history shows it was **wallstbots**
that was missing it. The code is fixed and live on all 3 sites either way — this is purely
a wrong site-name in an old note that could mislead someone later. I'll correct it.

---

## 4. ✅ RESOLVED — local file checked, no corruption found

Re-checked your local copy of `Frontends/wallstbots.tech/data/state.json` directly: it's
complete, valid JSON ending cleanly, with current live data for all 5 wallstbots bots. The
"corrupted" snapshot from earlier in the audit was most likely caught mid-write during a
refresh run. Nothing to discard — the file is fine.

---

## 5. ❓ Can't be verified by me — needs your eyes or DB access

- **The database's `origin_platform` constraint** — lives in Supabase directly, not
  something I can grep from files.
- **BOT13-Spotlight sub-features** (the "BOT13 + 4 more" card, the specific chatbot FAQ
  wording, the proof bar copy) — the overall feature is confirmed live, but I didn't
  re-verify every individual line of copy from that doc word-for-word.

---

## What I'd recommend doing next

1. Fix the aistocks $49,000 hardcode (small, isolated, 5-minute fix).
2. I'll correct the PROJECT_STATUS.md documentation error.
3. You discard the stray corrupted local data file (or tell me to and I will).
4. Everything else: no action needed — it's live and working.

Tell me which of 1–3 you want done now and I'll do them as separate, small changes per
Rule 1 (one concern per change) rather than bundling them together.
