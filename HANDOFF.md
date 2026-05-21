# WallStBots — Handoff Document
**Date:** May 20, 2026  
**Status:** Admin system built + deployed. JWT auth fix committed, push pending.

---

## ✅ What's Done

### Backend (FastAPI on Cloud Run)
- **v2.0 deployed** with full admin system: `/admin/stats`, `/admin/users`, `/admin/grant`, `/admin/promo-codes`
- Admin role bypass: admin users get unlimited bot access, all subscription checks pass
- PROMO CODE: `KING13` — 100% off any plan (seeded in DB)
- Admin account: `lvl13cs@gmail.com` — granted admin role in DB

### Frontend (Cloudflare Pages — wallstbots.tech)
- `admin.html` built: user management table, system stats, promo code creation, revoke access
- **getToken() fix applied locally** — reads `wallstbots_jwt` key (matches auth.js)
- `auth.js` — WallStBotsAuth class, stores token as `wallstbots_jwt`

### Database (Supabase — rfsssoeyctobxbhpjyom)
- `users` table has `role` column (user/admin) and `max_free_bots`
- `promo_codes` table seeded with KING13
- Email confirmation issue resolved (admin confirmed via Supabase Admin API)

---

## 🔧 One Remaining Step: Push + Redeploy

The ES256 JWT fix is committed locally but not yet pushed to GitHub.

### The Fix
New Supabase keys (`sb_publishable_`) produce **ES256** (asymmetric) JWTs.  
The old backend only verified **HS256** (symmetric). Admin panel was returning `{"detail":"Invalid token"}`.

**What was changed in `Backend/main.py`:**
1. Added `from jwt import PyJWKClient` import
2. `get_current_user()` now tries HS256 first, falls back to ES256 via Supabase JWKS endpoint

**Commit ready:** `75f7636` — "Fix ES256 JWT auth + admin.html getToken key mismatch"

---

## 🚀 Steps to Complete

### Step 1 — Push to GitHub (30 seconds)
Run the included script: **`push-jwt-fix.ps1`** (right-click → Run with PowerShell)

Or manually in PowerShell:
```powershell
cd "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
Remove-Item .git\index.lock,.git\refs\heads\master.lock -Force -ErrorAction SilentlyContinue
git push origin master
```

### Step 2 — Redeploy Backend to Cloud Run (~3-4 min)
In Google Cloud Shell (https://shell.cloud.google.com):
```bash
cd ~/wallstbots/Backend && git pull origin master && gcloud run deploy wallstbots-backend --source . --region us-east1 --allow-unauthenticated --quiet --project lvl13-tracker-496402
```

### Step 3 — Verify Admin Panel
1. Go to https://wallstbots.tech/admin
2. Log in with `lvl13cs@gmail.com`
3. Should see system stats (users, revenue, bots)
4. Test creating a promo code from the admin panel

---

## 🔑 Key Config Reference

| Item | Value |
|------|-------|
| Cloud Run service | `wallstbots-backend` (us-east1) |
| GCP Project | `lvl13-tracker-496402` |
| Supabase Project | `rfsssoeyctobxbhpjyom` |
| Backend URL | `https://wallstbots-backend-868128114349.us-east1.run.app` |
| Admin URL | `https://wallstbots.tech/admin` |
| Admin Account | `lvl13cs@gmail.com` |
| Promo Code | `KING13` (100% off) |

---

## 📁 Files Changed This Session

| File | Change |
|------|--------|
| `Backend/main.py` | ES256 JWT fix — `get_current_user()` + `PyJWKClient` import |
| `Frontends/wallstbots.tech/admin.html` | `getToken()` reads `wallstbots_jwt` (was `auth_token`) |

---

## ⚙️ Quick Verification

After redeploy, test with:
```bash
# Get a fresh token by logging in first, then:
curl -H "Authorization: Bearer TOKEN" \
  https://wallstbots-backend-868128114349.us-east1.run.app/admin/stats
# Should return: {"total_users":N,"total_revenue":N,"active_bots":N,"recent_signups":[...]}
```

*Built by Claude — WallStBots v2.0*
