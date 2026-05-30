# WallStBots — Project Handoff Document
**Date:** May 28, 2026  
**Repo:** https://github.com/lvl13tech/wallstbots  
**Owner:** M13 / lvl13cs@gmail.com

---

## 1. What This Project Is

Three public-facing websites that function as one platform, each focused on a different market segment:

| Domain | Focus | Hosting |
|---|---|---|
| wallstbots.tech | Stock market (broad) | Cloudflare Pages |
| lvl13.tech | AI & quantum stocks | Cloudflare Pages |
| bitbot13.tech | Cryptocurrency | Cloudflare Pages |

All three sites are identical in design and functionality. The only differences are branding, the ticker universe the bots trade, and the `platform=` parameter passed to the backend API.

---

## 2. Architecture Overview

```
GitHub Repo (lvl13tech/wallstbots)
│
├── Frontends/
│   ├── wallstbots.tech/     ← deployed to Cloudflare Pages
│   ├── lvl13.tech/          ← deployed to Cloudflare Pages
│   └── bitbot13.tech/       ← deployed to Cloudflare Pages
│
├── Backend/
│   └── main.py              ← FastAPI, deployed to Google Cloud Run
│
└── Project/scripts/
    ├── refresh_wallstbots.py
    ├── refresh_lvl13.py
    ├── refresh_bitbot13.py
    └── bot13_engine.py      ← shared BOT13 decision logic
```

**Frontend deploy:** `git push origin master` → Cloudflare auto-deploys all 3 sites.  
**Backend deploy:** `DEPLOY-BACKEND.bat` → pushes to GitHub → GitHub Actions builds Docker image → deploys to Cloud Run.

---

## 3. Key Services & Credentials

| Service | What It Does | Where to Find Credentials |
|---|---|---|
| **Google Cloud Run** | Hosts the FastAPI backend | GCP Console → `wallstbots-backend` service in `us-east1` |
| **Supabase** | User auth (JWT), database (holdings, portfolios, email prefs) | Supabase dashboard → env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` |
| **Firebase / Firestore** | User tier storage (member/insider/syndicate/webmaster) | GCP Console → Firestore |
| **Resend** | Transactional email (signals, alerts) | resend.com → API key in GitHub Secret `RESEND_API_KEY` |
| **PayPal** | Subscription billing | PayPal dashboard |
| **GitHub Actions** | Auto-runs refresh scripts on schedule | github.com/lvl13tech/wallstbots/actions |

**Backend URL:** `https://wallstbots-backend-868128114349.us-east1.run.app`

---

## 4. How the Bots Work

Each site has 5 bots: **BOT13, ORACLE, WIZARD, EQUALIZER, TITAN**

### BOT13 (the primary AI bot)
- Runs on a live decision engine (`bot13_engine.py`)
- Each refresh cycle: pulls top momentum stocks, scores them, selects picks if projected return ≥ 1.74%
- Decision is either **TRADE** (enters positions) or **HOLD** (stays in cash)
- **Key rule:** If the last decision was TRADE, picks and positions are preserved in all subsequent HOLD states until the next TRADE fires. This is the intended "stale data" behavior — the page should always show the last active trade, not go blank.
- Stop loss: -1.5% | Target: +3.0%

### ORACLE, WIZARD
- Rule-based momentum bots
- ORACLE uses weekly momentum + weekend holding_cash logic
- WIZARD uses trend-following

### EQUALIZER, TITAN
- Seeded at inception with fixed position allocations
- Value compounds via snapshots over time

---

## 5. Refresh Schedule (GitHub Actions)

| Workflow | Sites | Schedule (ET) |
|---|---|---|
| `refresh-lvl13.yml` | lvl13.tech | 10:35 AM, 12:05 PM, 5:05 PM — weekdays |
| `refresh-wallstbots.yml` | wallstbots.tech | 10:35 AM, 12:05 PM, 5:05 PM — weekdays |
| `refresh-bitbot13.yml` | bitbot13.tech | Every 30 min, 9 AM – 7 PM — daily |

**To trigger manually:** Go to GitHub → Actions → select workflow → "Run workflow"

---

## 6. Deployment — Step by Step

### Deploying frontend changes (all 3 sites)
```
1. Make changes in Frontends/wallstbots.tech/, Frontends/lvl13.tech/, Frontends/bitbot13.tech/
2. Run any PUSH-*.bat file in the WallStBots root folder
   (they all do: git add → git commit → git pull --rebase → git push)
3. Cloudflare auto-deploys within ~60 seconds
```

### Deploying backend changes
```
1. Edit Backend/main.py
2. Run DEPLOY-BACKEND.bat
   (builds Docker image → pushes to Artifact Registry → deploys to Cloud Run via GitHub Actions)
```

### Deploying refresh script changes
```
1. Edit Project/scripts/refresh_lvl13.py (or wallstbots/bitbot13)
2. Run PUSH-refresh-script-fix.bat (or any PUSH bat)
3. git push → GitHub Actions picks up the new script on next scheduled run
4. To test immediately: trigger workflow manually on GitHub Actions
```

---

## 7. File Structure — Each Frontend

```
Frontends/wallstbots.tech/
├── index.html           ← public homepage (bot tracker + pricing)
├── dashboard.html       ← member dashboard (requires login)
├── bot-detail.html      ← individual bot fund page
├── portfolio-fund.html  ← per-user portfolio tracker
├── leaderboard.html     ← community leaderboard
├── auth.html            ← login / signup
├── api.js               ← all backend API calls
├── auth.js              ← JWT auth handling
├── assets/
│   └── app.js           ← homepage tracker logic
└── data/
    └── state.json       ← bot state snapshot (read by Cloudflare Pages)
```

---

## 8. state.json — Data Flow

The refresh scripts write bot state to two places:
1. **Backend** (Cloud Run) — via POST to `/tracker/update?platform=wallstbots`
2. **Frontend** — `Frontends/[site]/data/state.json` is committed to GitHub → Cloudflare serves it as a static file

The homepage reads `state.json` directly (no auth required). The member dashboard reads from the live backend API (requires JWT).

**state.json structure:**
```json
{
  "funds": {
    "bot13": {
      "value": { "total": 66318.32, "positions": [...] },
      "current_strategy": {
        "decision": "TRADE",
        "day": "2026-05-28",
        "picks": [...],
        "rationale": "...",
        "projected_return": 4.59,
        "session_log": [...]
      }
    },
    "oracle": { ... },
    "wizard": { ... },
    "equalizer": { ... },
    "titan": { ... }
  },
  "snapshots": [
    { "date": "2026-05-21", "funds": { "bot13": 57524.57, ... } }
  ],
  "last_refresh": "2026-05-28T17:05:00Z"
}
```

---

## 9. Known Issues & Current Status (as of May 28, 2026)

### ✅ Recently Fixed
- **New-day HOLD wipes picks** — When market closed overnight, the refresh script was clearing BOT13 picks on the next day's HOLD cycle. Fixed in all 3 scripts: picks/positions are now preserved whenever the previous decision was TRADE, regardless of which day that trade fired.
- **BOT13 HOLD branch** — Now correctly carries forward `positions`, `picks`, `rationale`, `projected_return`, and `session_log` from the last TRADE.

### ⚠️ Pending Deployment
- The refresh script fix (Task #171) is committed but the push to GitHub may still be pending if `PUSH-refresh-script-fix.bat` has not successfully completed. The bat uses `git stash → git pull --rebase → git stash pop → git push`. Run it and verify on GitHub Actions.

### 📋 Open Feature Work
From the full-stack audit (`WallStBots_Feature_Audit_2026-05-28.md`):
- Password reset flow (forgot password link missing from login page)
- Stripe integration + full subscription lifecycle (upgrade/downgrade/cancel)
- CSV / Excel data export
- Notification preferences panel
- Date range picker on charts

---

## 10. Membership Tiers

| Tier | Monthly | Annual | Portfolios |
|---|---|---|---|
| Member | $49.99 | — | 3 |
| Insider | $69.99 | — | 10 |
| Syndicate | $99.99 | — | 25 |
| Webmaster | Internal | — | 99 |

Tiers are stored in **Firestore** per user. The backend checks the tier on every authenticated API call. To promote a user: Firestore → `users` collection → set `tier` field.

---

## 11. Admin Access

- **Webmaster dashboard:** Log in at `/dashboard.html` with a webmaster-tier account → "System" tab appears
- **Admin endpoints** (require webmaster JWT): `/webmaster/users`, `/webmaster/system`, `/webmaster/signals`, etc.
- **Your account** (`lvl13cs@gmail.com`) is set to webmaster tier in Firestore

---

## 12. Quick Reference — Common Tasks

| Task | How |
|---|---|
| Deploy frontend change | Edit file → run any `PUSH-*.bat` |
| Deploy backend change | Edit `Backend/main.py` → run `DEPLOY-BACKEND.bat` |
| Manually trigger bot refresh | GitHub Actions → select workflow → Run workflow |
| Promote user to a tier | Firestore → users → set `tier` field |
| Check backend logs | GCP Console → Cloud Run → `wallstbots-backend` → Logs |
| Check GitHub Actions runs | github.com/lvl13tech/wallstbots/actions |
| View live bot state (no auth) | `https://wallstbots-backend-868128114349.us-east1.run.app/public/tracker/state?platform=wallstbots` |
