# Wall St. Bots - Quick Start Guide for New Developers

**Goal:** Get up to speed on the Wall St. Bots project in 30 minutes  
**Prerequisites:** Git, Docker (optional), basic knowledge of web development

---

## 5-Minute Overview

Wall St. Bots is a unified trading bot platform (stocks, crypto, AI trading) with:
- **Backend:** FastAPI running on Google Cloud Run
- **Frontend:** Three independent HTML/JS sites (lvl13.tech, bitbot13.tech, wallstbots.tech)
- **Database:** PostgreSQL via Supabase
- **Hosting:** Cloudflare Pages for frontends, Cloud Run for API

**Current Status:** Backend is live and working. Frontends are deployed but DNS configuration still in progress.

---

## Access Accounts You'll Need

| Service | Account | URL |
|---------|---------|-----|
| GitHub | lvl13tech | https://github.com/lvl13tech |
| Google Cloud | (check project ID in console) | https://console.cloud.google.com |
| Cloudflare | (check account) | https://dash.cloudflare.com |
| GoDaddy | (domain owner) | https://www.godaddy.com |
| Supabase | (check project) | https://supabase.com |

---

## Get the Code

```bash
# Clone repository
git clone https://github.com/lvl13tech/wallstbots.git
cd wallstbots

# See what's in the repo
ls -la
# Shows: Backend/, Frontends/, .git/, .gitignore

# See GitHub commits
git log --oneline
```

---

## Understand the Frontend

**Frontend code is simple HTML + JavaScript:**

```
Frontends/
├── lvl13.tech/          # Main hub - shows ALL bot types
│   ├── index.html       # Dashboard
│   ├── login.html       # Login form
│   ├── signup.html      # Registration form
│   ├── auth.js          # Authentication code
│   └── api.js           # API communication
├── bitbot13.tech/       # Crypto-specific dashboard
└── wallstbots.tech/     # Stock-specific dashboard
```

**How frontends work:**
1. Page loads → checks if user is logged in
2. If not logged in → redirect to login.html
3. On login → stores token in browser storage
4. On dashboard → calls backend API to get user's bots
5. Displays bot cards with performance metrics

**Key files:**
- `auth.js` - Handles user login/logout
- `api.js` - Talks to backend API
- `index.html` - Dashboard that loads bots

**API is hardcoded in each file:**
```javascript
const API_BASE_URL = "https://wallstbots-backend-868128114349.us-east1.run.app";
```

---

## Understand the Backend

**Backend is FastAPI (Python):**

```
Backend/
├── main.py              # Entire application
├── Dockerfile           # How to package it
├── requirements.txt     # Python dependencies
├── .env                 # Secrets (NOT in git)
└── supabase.env         # Database secrets (NOT in git)
```

**Key functions in main.py:**
- `POST /auth/signup` - Register new user
- `POST /auth/login` - User login
- `GET /user/profile` - Get current user
- `GET /bots` - List user's bots
- `GET /bots/{id}` - Get specific bot details
- `POST /bots` - Create new bot

**Test the API:**
```bash
# Check if backend is running
curl https://wallstbots-backend-868128114349.us-east1.run.app/health

# Should return: {"status": "ok"}
```

---

## What's Running Now

### ✅ Live in Production

**API Backend:**
- URL: https://wallstbots-backend-868128114349.us-east1.run.app
- Status: Running on Google Cloud Run
- Try it: https://wallstbots-backend-868128114349.us-east1.run.app/docs (API explorer)

**Frontends (Pages):**
- bitbot13.tech (deployed via Cloudflare Pages)
- lvl13.tech (not yet deployed - DNS pending)
- wallstbots.tech (not yet deployed - DNS pending)

### 🔴 Not Yet Deployed

- DNS configuration for lvl13.tech and wallstbots.tech domains
- Custom domain mapping for bitbot13.tech on Cloudflare

---

## Next Immediate Steps

**Today:** Complete DNS setup

```
1. Open Cloudflare Dashboard
2. Go to Pages → wallstbots project
3. Click Custom Domains
4. Enter: bitbot13.tech
5. Copy Cloudflare nameservers shown
6. Log into GoDaddy
7. Update nameservers for bitbot13.tech
8. Wait 24-48 hours for DNS to propagate
```

**This Week:** Create other Pages projects

```
1. Create Pages project for lvl13.tech
   - GitHub: wallstbots repo
   - Build output: Frontends/lvl13.tech
2. Create Pages project for wallstbots.tech
   - GitHub: wallstbots repo
   - Build output: Frontends/wallstbots.tech
3. Add custom domains to each
4. Update GoDaddy nameservers for each domain
```

---

## Common Tasks

### View Backend Logs

```bash
# Install Google Cloud CLI first
gcloud init

# View recent logs
gcloud run logs read wallstbots-backend --region=us-east1 --limit=50

# Watch logs in real-time
gcloud run logs read wallstbots-backend --region=us-east1 --follow
```

### Deploy Updated Backend Code

```bash
# 1. Make changes to Backend/main.py

# 2. Build and push new Docker image
cd Backend
docker build -t lvl13tech/wallstbots:latest .
docker push lvl13tech/wallstbots:latest

# 3. Redeploy to Cloud Run (via Google Cloud console)
# Go to: Cloud Run → wallstbots-backend → Deploy New Revision
# Image: lvl13tech/wallstbots:latest
```

### Deploy Updated Frontend Code

```bash
# 1. Edit files in Frontends/bitbot13.tech/
# 2. Commit and push to GitHub
git add Frontends/
git commit -m "Update bitbot13.tech dashboard"
git push origin master

# 3. Cloudflare Pages auto-redeploys when GitHub updates
# Check status in: https://dash.cloudflare.com → Pages
```

### Test Frontend Locally

```bash
# Option 1: Simple Python server
cd Frontends/bitbot13.tech
python -m http.server 8000
# Visit http://localhost:8000

# Option 2: Use any web server
# Just serve the HTML file with HTTP (not file://)
```

---

## Important Files to Know

### .env File (Backend - NOT in Git)

This file contains secrets and is NOT committed. Keep it safe:

```
PAYPAL_CLIENT_ID=your_paypal_id
PAYPAL_SECRET=your_paypal_secret
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_supabase_key
```

If you lose this file:
1. Check with original developer (M13)
2. Or recreate from Supabase and PayPal dashboards

### .gitignore File (In Git)

This tells Git which files to ignore:
```
.env
supabase.env
__pycache__/
*.pyc
node_modules/
```

**Important:** Always add secrets to `.gitignore` BEFORE committing!

---

## Troubleshooting Checklist

### Frontend shows "API Error"

1. Check API is running:
   ```bash
   curl https://wallstbots-backend-868128114349.us-east1.run.app/health
   ```
2. Check frontend HTML has correct API URL
3. Check browser console for CORS errors
4. Check Cloud Run logs for backend errors

### Can't access a frontend domain

1. Check DNS propagation: `nslookup bitbot13.tech`
2. Should show Cloudflare nameservers (ns1.cloudflare.com)
3. If not propagated, wait 24-48 hours
4. Check Cloudflare Pages project is deployed

### Backend won't start

1. Check Python dependencies: `pip install -r requirements.txt`
2. Check .env file exists with all required values
3. Check Port is available (not running twice)
4. Check logs: `gcloud run logs read wallstbots-backend`

---

## Key Contacts & Resources

**Original Developer:** M13 (lvl13cs@gmail.com)

**Services Support:**
- Google Cloud: https://console.cloud.google.com
- Cloudflare: https://support.cloudflare.com
- Supabase: https://supabase.com/support
- GoDaddy: https://www.godaddy.com/help

**Documentation in this folder:**
- `HANDOFF.md` - Complete handoff document
- `TECHNICAL_REFERENCE.md` - Deep technical details
- `QUICKSTART.md` - This file

---

## What to Do First

1. **Read HANDOFF.md** (10 min) - Understand current status
2. **Review TECHNICAL_REFERENCE.md** (20 min) - Learn architecture
3. **Clone the GitHub repo** (5 min) - Get the code
4. **Test the backend API** (5 min) - Verify it's working
5. **Complete DNS setup** (30 min over 2 days) - Get domains live

**Total time to productive:** ~1 hour + DNS wait time

---

## You're Ready!

Start with the tasks in HANDOFF.md under "Next Steps for Handoff Owner". Good luck! 🚀
