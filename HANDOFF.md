# Wall St. Bots - Project Handoff Document

**Date:** May 17, 2026  
**Status:** In Progress - Deployment Phase 2  
**Owner:** M13 (lvl13cs@gmail.com)

---

## Executive Summary

Wall St. Bots is a unified trading bot platform with three integrated frontends (Level XIII Tech, BitBot13, Wall St. Bots) running on a shared FastAPI backend deployed to Google Cloud Run. Phase 1 (backend & initial deployment) is complete. Phase 2 (Cloudflare Pages DNS configuration) is in progress.

---

## Current Deployment Status

### ✅ Completed

**Backend:**
- FastAPI application with Supabase Auth, PostgreSQL, and PayPal integration
- Successfully deployed to Google Cloud Run at: `https://wallstbots-backend-868128114349.us-east1.run.app`
- Docker image fixed to read `PORT` environment variable correctly
- Docker Hub image: `lvl13tech/wallstbots:latest` (sha256: 41c9b36a84d871ebcdc6ac0bd26f2ab237813839c8fad53d67d74ccfa198b3ab)

**Frontend Updates:**
- All three frontends updated with correct Cloud Run API URL
- lvl13.tech (Level XIII Tech hub) - serves all bot types
- bitbot13.tech (Crypto trading bots)
- wallstbots.tech (Stock portfolio tracking)

**Version Control:**
- Repository initialized and code pushed to GitHub: `https://github.com/lvl13tech/wallstbots.git`
- .env and supabase.env files excluded from git tracking (credentials protected)
- Commit history maintained with proper messages

**Cloudflare Pages - First Project:**
- Project created: "wallstbots"
- Build output directory: `Frontends/bitbot13.tech`
- Status: ✅ Successfully deployed
- Last deployment: May 17, 2026

---

## 🔴 In Progress / Pending

### Phase 2: Cloudflare Pages & DNS Configuration

**Status:** Partially started - Cloudflare dashboard loading issues encountered

**Pending Tasks:**

1. **Add Custom Domain to wallstbots Pages Project**
   - Domain: `bitbot13.tech`
   - Where: Cloudflare Dashboard → Pages → wallstbots → Custom Domains
   - Action: Enter domain and follow DNS configuration step

2. **Create lvl13.tech Pages Project**
   - GitHub repository: https://github.com/lvl13tech/wallstbots.git
   - Build output directory: `Frontends/lvl13.tech`
   - Custom domain: `lvl13.tech`

3. **Create wallstbots.tech Pages Project**
   - GitHub repository: https://github.com/lvl13tech/wallstbots.git
   - Build output directory: `Frontends/wallstbots.tech`
   - Custom domain: `wallstbots.tech`

4. **Configure DNS Nameservers (GoDaddy)**
   - For each domain (bitbot13.tech, lvl13.tech, wallstbots.tech):
     - Log into GoDaddy domain settings
     - Update nameservers to Cloudflare's nameservers (Cloudflare will provide these)
     - Wait 24-48 hours for DNS propagation

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Cloudflare CDN                         │
├────────────────┬────────────────┬────────────────────────┤
│                │                │                        │
│  bitbot13.tech │  lvl13.tech    │ wallstbots.tech       │
│  (Cloudflare   │  (Cloudflare   │ (Cloudflare Pages)    │
│   Pages)       │   Pages)       │                        │
└────────────────┴────────────────┴────────────────────────┘
                          │
                          ↓
┌─────────────────────────────────────────────────────────┐
│         Google Cloud Run (FastAPI Backend)               │
│  https://wallstbots-backend-868128114349.us-east1.run.app
├─────────────────────────────────────────────────────────┤
│  • Authentication (Supabase Auth)                        │
│  • Database (Supabase PostgreSQL)                        │
│  • Payment Processing (PayPal)                           │
│  • Bot Logic & Performance Tracking                      │
└─────────────────────────────────────────────────────────┘
```

---

## Important URLs & Credentials

### Production Endpoints

| Component | URL |
|-----------|-----|
| **API Backend** | https://wallstbots-backend-868128114349.us-east1.run.app |
| **GitHub Repository** | https://github.com/lvl13tech/wallstbots.git |
| **Supabase Project** | Dashboard at https://supabase.com (credentials in Backend/supabase.env) |
| **PayPal Integration** | Credentials in Backend/.env (not in git) |

### Cloudflare Accounts

- Dashboard: https://dash.cloudflare.com
- Check status page if dashboard is unresponsive: https://www.cloudflarestatus.com

### GoDaddy Domain Management

- Login at: https://www.godaddy.com
- Manage domains: Domain Settings → Nameservers

### Docker Hub

- Image repository: `lvl13tech/wallstbots`
- Latest tag: `latest`
- Full image name: `lvl13tech/wallstbots:latest`

---

## Key Configuration Files

### Backend (`Backend/` folder)

| File | Purpose | Git Status |
|------|---------|-----------|
| `main.py` | FastAPI application entry point | ✅ In Git |
| `Dockerfile` | Container definition (FIXED: reads PORT env var) | ✅ In Git |
| `requirements.txt` | Python dependencies | ✅ In Git |
| `.env` | PayPal & API credentials | ❌ NOT in Git (security) |
| `supabase.env` | Supabase credentials | ❌ NOT in Git (security) |
| `.gitignore` | Excludes .env files | ✅ In Git |

### Frontends (Frontends/ folders)

Each frontend has three files with updated API URL:

- `index.html` - Main dashboard (loads bots from API)
- `login.html` - Authentication page
- `signup.html` - User registration page

API URL set in each: `const API_BASE_URL = "https://wallstbots-backend-868128114349.us-east1.run.app";`

---

## Frontend Files Status

### ✅ Updated with Correct API URL

1. **Frontends/lvl13.tech/**
   - index.html ✅
   - login.html ✅
   - signup.html ✅

2. **Frontends/bitbot13.tech/**
   - index.html ✅

3. **Frontends/wallstbots.tech/**
   - index.html ✅

### Shared Assets

- **Frontends/lvl13.tech/auth.js** - Authentication module (used by all platforms)
- **Frontends/lvl13.tech/api.js** - API client (used by all platforms)

---

## Deployment Checklist

- [x] Backend Docker image built & pushed to Docker Hub
- [x] Backend deployed to Google Cloud Run
- [x] Frontend API URLs updated to Cloud Run endpoint
- [x] Code committed and pushed to GitHub
- [x] Cloudflare Pages first project created (wallstbots)
- [ ] Add bitbot13.tech custom domain to wallstbots Pages project
- [ ] Create lvl13.tech Cloudflare Pages project
- [ ] Create wallstbots.tech Cloudflare Pages project
- [ ] Configure DNS nameservers at GoDaddy for all three domains
- [ ] Test all three frontends are live and functioning
- [ ] Verify cross-platform login works (one login for all three)

---

## Next Steps for Handoff Owner

### Immediate (Today)

1. **Wait for Cloudflare Dashboard to Become Responsive**
   - Check https://www.cloudflarestatus.com for any ongoing issues
   - Try accessing dashboard from a different browser/incognito window
   - If still unresponsive, contact Cloudflare support

2. **Once Dashboard Loads:**
   - Go to wallstbots Pages project
   - Navigate to Custom Domains tab
   - Enter `bitbot13.tech` as custom domain
   - Follow DNS configuration instructions (you'll get Cloudflare nameservers)

### Short Term (Next 2-3 Days)

3. **Create lvl13.tech Pages Project:**
   - Pages → Create Project → Connect GitHub
   - Select: wallstbots repository
   - Build output directory: `Frontends/lvl13.tech`
   - Add custom domain: `lvl13.tech`

4. **Create wallstbots.tech Pages Project:**
   - Repeat process for `wallstbots.tech` domain
   - Build output directory: `Frontends/wallstbots.tech`

5. **Update GoDaddy Nameservers:**
   - For each domain, go to GoDaddy → Domain Settings
   - Replace nameservers with Cloudflare's nameservers
   - **Important:** This step required for custom domains to work

6. **Verify Deployment:**
   - Test accessing all three domains
   - Verify login works on each platform
   - Confirm API calls reach backend correctly
   - Test bot creation/viewing functionality

### Medium Term (Week 2)

7. **Implement Remaining Features:**
   - PayPal promo code logic (currently in progress)
   - Tracker engine integration (currently in progress)
   - Monitor Cloud Run logs for errors
   - Set up error alerting/monitoring

---

## Troubleshooting Guide

### Issue: Cloudflare Dashboard Won't Load

**Symptoms:** Loading spinner persists indefinitely

**Solutions:**
1. Check Cloudflare status page: https://www.cloudflarestatus.com
2. Try incognito/private window
3. Clear browser cache (Ctrl+Shift+Delete)
4. Try different browser
5. Contact Cloudflare support if issue persists

### Issue: Frontend Shows "API Error" or "Loading Forever"

**Likely Cause:** API endpoint unreachable or not responding

**Debug Steps:**
1. Verify API URL in frontend HTML matches Cloud Run URL exactly
2. Check Cloud Run service is running: https://console.cloud.google.com/run
3. Check backend logs in Cloud Run console
4. Verify no CORS issues (may need to update backend CORS settings)
5. Test API directly: `curl https://wallstbots-backend-868128114349.us-east1.run.app/health`

### Issue: DNS Not Propagating

**Symptoms:** Domain still points to old nameservers after GoDaddy update

**Solutions:**
1. Wait 24-48 hours (DNS propagation delay)
2. Verify nameservers actually changed: `nslookup bitbot13.tech`
3. Check GoDaddy confirmed the change
4. If stuck after 48 hours, contact GoDaddy or Cloudflare support

### Issue: Login Redirects to Old Domain

**Likely Cause:** Frontend hardcoding old domain in redirect URL

**Fix:** Check login.html and signup.html for hardcoded redirects, update to correct domains

---

## Important Security Notes

⚠️ **Never Commit These Files to Git:**
- `.env` (contains PayPal secrets)
- `supabase.env` (contains Supabase secret keys)
- Any API keys or passwords

✅ **These Are Safely Excluded:**
- Files are in `.gitignore`
- GitHub push protection blocked attempted commits with secrets
- Keep local copies safe on secure machines

---

## Contact & Support

**Original Developer:** M13  
**Email:** lvl13cs@gmail.com  
**GitHub Account:** lvl13tech  

**Services:**
- Cloudflare Support: https://support.cloudflare.com
- Google Cloud Support: https://cloud.google.com/support
- Supabase Support: https://supabase.com/support
- GoDaddy Support: https://www.godaddy.com/help

---

## Document Revision History

| Date | Changes |
|------|---------|
| May 17, 2026 | Initial handoff document created |

---

**Last Updated:** May 17, 2026
