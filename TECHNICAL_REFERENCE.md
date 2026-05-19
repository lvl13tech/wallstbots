# Wall St. Bots - Technical Reference Guide

**Purpose:** Deep technical documentation for developers continuing the project  
**Audience:** Backend/DevOps engineers, frontend developers  
**Last Updated:** May 17, 2026

---

## Project Structure

```
wallstbots/
├── Backend/                          # FastAPI backend (Python)
│   ├── main.py                      # FastAPI application entry point
│   ├── Dockerfile                   # Container image definition
│   ├── requirements.txt              # Python dependencies
│   ├── .env                         # Environment variables (NOT in git)
│   ├── supabase.env                 # Supabase credentials (NOT in git)
│   └── .gitignore                   # Excludes sensitive files
│
├── Frontends/                        # Static frontends
│   ├── lvl13.tech/                  # Level XIII Tech hub
│   │   ├── index.html               # Dashboard for all bot types
│   │   ├── login.html               # Login page
│   │   ├── signup.html              # Registration page
│   │   ├── auth.js                  # Auth module (shared with other frontends)
│   │   └── api.js                   # API client module (shared)
│   │
│   ├── bitbot13.tech/               # Crypto trading bots
│   │   └── index.html               # Crypto dashboard
│   │
│   └── wallstbots.tech/             # Stock portfolio tracking
│       └── index.html               # Stock dashboard
│
└── .git/                             # Git version control

```

---

## Backend Architecture

### FastAPI Application (main.py)

**Core Components:**

1. **Authentication** - Supabase Auth
   - User signup/login endpoints
   - Token validation
   - Cross-platform session management

2. **Database** - PostgreSQL via Supabase
   - User accounts
   - Bot configurations
   - Portfolio performance history
   - Tracking data

3. **Bot Management**
   - Create/read/update/delete bots
   - Multi-platform support (wallstbots, bitbot13, lvl13)
   - Performance calculations
   - Return/gain-loss tracking

4. **Payment Integration** - PayPal
   - Promo code handling
   - Referral discount logic (in progress)

5. **APIs**
   - `GET /health` - Health check
   - `POST /auth/signup` - User registration
   - `POST /auth/login` - User authentication
   - `GET /user/profile` - User information
   - `GET /bots` - List user's bots
   - `GET /bots/{id}` - Get specific bot
   - `POST /bots` - Create new bot
   - (See OpenAPI docs at `/docs` when running)

### Docker Configuration

**Dockerfile Strategy:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

**Key Fix Applied:**
- Changed from hardcoded `--port 8000` to reading `PORT` environment variable
- `port = int(os.environ.get("PORT", 8000))` in main.py
- Allows Cloud Run to dynamically assign ports

**Building & Pushing:**
```bash
docker build -t lvl13tech/wallstbots:latest .
docker push lvl13tech/wallstbots:latest
```

### Google Cloud Run Deployment

**Service Details:**
- **Region:** us-east1
- **URL:** https://wallstbots-backend-868128114349.us-east1.run.app
- **Image:** lvl13tech/wallstbots:latest
- **Memory:** (check Cloud Run console for specs)
- **Concurrency:** (check Cloud Run console for settings)

**Environment Variables in Cloud Run:**
- `PORT=8080` (set automatically by Cloud Run)
- Any additional config should be added via Cloud Run UI

**Logs Access:**
- Cloud Console: https://console.cloud.google.com/logs
- CLI: `gcloud run logs read wallstbots-backend --region=us-east1`

---

## Frontend Architecture

### Technology Stack

- **HTML5** - Markup
- **CSS3** - Styling (inline in HTML files)
- **Vanilla JavaScript** - No frameworks (lightweight, fast)
- **Fetch API** - HTTP requests

### API Integration

**Each frontend loads two JavaScript modules from lvl13.tech:**

1. **auth.js** - Authentication helper class
   - `WallStBotsAuth(apiBaseUrl)`
   - Methods: `login()`, `signup()`, `logout()`, `isAuthenticated()`
   - Stores token in localStorage

2. **api.js** - API client class
   - `WallStBotsAPI(apiBaseUrl, authInstance)`
   - Methods: `getUserProfile()`, `getBots()`, `getBot(id)`
   - Automatically includes auth token in requests

### Frontend Workflow

1. **Page loads** → checks authentication
2. **If not authenticated** → redirect to login.html
3. **On login success** → redirect to index.html (dashboard)
4. **Dashboard loads** → calls `api.getBots()`
5. **For each bot** → calls `api.getBot(botId)` to get performance data
6. **Renders bot cards** with latest performance metrics

### API URL Configuration

**Currently set to:**
```javascript
const API_BASE_URL = "https://wallstbots-backend-868128114349.us-east1.run.app";
```

**Location in each file:**
- Search for `const API_BASE_URL =` in index.html, login.html, signup.html
- Update if backend URL changes

### Performance Data Display

Each dashboard shows:
- Bot name
- Platform (wallstbots/bitbot13/lvl13)
- Portfolio value: `perf.total_value`
- Return percentage: `perf.gain_loss_pct`
- Creation date: `bot.created_at`

---

## GitHub Repository Management

**Repository:** https://github.com/lvl13tech/wallstbots.git

### Committing Code

**Safe to commit:**
- Backend code (main.py, requirements.txt, Dockerfile)
- Frontend code (all HTML/JS files)
- Configuration (setup scripts, documentation)

**Never commit:**
- `.env` - Contains PayPal API keys
- `supabase.env` - Contains Supabase secret keys
- `node_modules/`, `__pycache__/`, `.DS_Store`
- Any API keys, tokens, or credentials

### Git Workflow

```bash
# Pull latest changes
git pull origin master

# Make changes to files
# ... edit files ...

# Stage and commit
git add .
git commit -m "Description of changes"

# Push to GitHub
git push origin master
```

### GitHub Push Protection

GitHub automatically blocks commits containing:
- Supabase secret keys
- PayPal API keys
- Database passwords
- JWT tokens

If push is blocked:
1. Remove the secret from the commit: `git rm --cached <file>`
2. Add to `.gitignore` if not already there
3. Amend the commit: `git commit --amend`
4. Force push: `git push -f origin master`

---

## Cloudflare Pages Configuration

### Current Setup

**Project Name:** wallstbots  
**GitHub Repository:** https://github.com/lvl13tech/wallstbots  
**Build Output Directory:** `Frontends/bitbot13.tech`

### Pages Project Settings to Configure

When creating new Pages projects (for lvl13.tech and wallstbots.tech):

1. **Build Settings**
   - Build command: (leave blank - no build step needed)
   - Build output directory: `Frontends/<domain>`

2. **Environment Variables**
   - None required (API URL is hardcoded in HTML)

3. **Custom Domains**
   - Add domain after project creation
   - Cloudflare will provide nameservers

### DNS Configuration Process

1. **In Cloudflare Dashboard:**
   - Custom Domains → "Add Custom Domain"
   - Enter domain name (e.g., bitbot13.tech)
   - Click Continue
   - Copy Cloudflare nameservers shown

2. **In GoDaddy Domain Settings:**
   - Go to domain settings
   - Find "Nameservers" section
   - Replace default GoDaddy nameservers with Cloudflare ones
   - Save changes
   - **Wait 24-48 hours for propagation**

3. **Verify DNS Resolution:**
   ```bash
   # From terminal
   nslookup bitbot13.tech
   # Should show Cloudflare nameservers (ns1.cloudflare.com, etc.)
   ```

---

## Database Schema (Supabase PostgreSQL)

### Key Tables

**users**
- id (UUID, primary key)
- email (string, unique)
- password_hash (string)
- created_at (timestamp)

**bots**
- id (UUID, primary key)
- user_id (UUID, foreign key → users.id)
- name (string)
- platform (string: 'wallstbots', 'bitbot13', 'lvl13')
- created_at (timestamp)
- configuration (JSON)

**performances**
- id (UUID, primary key)
- bot_id (UUID, foreign key → bots.id)
- total_value (decimal)
- gain_loss_pct (decimal)
- recorded_at (timestamp)

(Note: Actual schema should be verified in Supabase console)

---

## Monitoring & Logging

### Cloud Run Logs

**View logs in real-time:**
```bash
gcloud run logs read wallstbots-backend --region=us-east1 --limit=100
```

**Search for errors:**
```bash
gcloud run logs read wallstbots-backend --region=us-east1 | grep -i error
```

### Common Issues to Monitor

1. **500 Internal Server Error** - Check logs for exception details
2. **401 Unauthorized** - Token validation failing
3. **503 Service Unavailable** - Backend not responding
4. **CORS errors** - Frontend can't reach API (check CORS configuration in main.py)

### Performance Metrics

Monitor in Google Cloud Console:
- Request latency
- Error rate
- CPU/Memory usage
- Concurrent requests

---

## Development Workflow

### Local Development Setup

**1. Install Python 3.11:**
```bash
python --version  # Should be 3.11+
```

**2. Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**3. Install dependencies:**
```bash
pip install -r Backend/requirements.txt
```

**4. Set environment variables:**
```bash
# Create Backend/.env with:
PAYPAL_CLIENT_ID=your_client_id
PAYPAL_SECRET=your_secret
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

**5. Run backend locally:**
```bash
cd Backend
python main.py
# Runs on http://localhost:8000
```

**6. Access API docs:**
- Visit http://localhost:8000/docs (Swagger UI)
- Visit http://localhost:8000/redoc (ReDoc)

### Testing the API

**Test health endpoint:**
```bash
curl https://wallstbots-backend-868128114349.us-east1.run.app/health
```

**Test signup:**
```bash
curl -X POST https://wallstbots-backend-868128114349.us-east1.run.app/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

---

## Common Tasks & Solutions

### Update API URL Across All Frontends

**Find and replace in all HTML files:**
```bash
grep -r "API_BASE_URL" Frontends/
# Shows all locations where API URL is defined
```

**Replace in specific files:**
```bash
# Edit Frontends/lvl13.tech/index.html
# Edit Frontends/lvl13.tech/login.html
# Edit Frontends/lvl13.tech/signup.html
# Edit Frontends/bitbot13.tech/index.html
# Edit Frontends/wallstbots.tech/index.html
# Search for: const API_BASE_URL = "..."
# Replace with: const API_BASE_URL = "https://new-url.example.com";
```

### Deploy Updated Docker Image

**1. Build image:**
```bash
cd Backend
docker build -t lvl13tech/wallstbots:latest .
```

**2. Push to Docker Hub:**
```bash
docker push lvl13tech/wallstbots:latest
```

**3. Redeploy to Cloud Run:**
- Go to: https://console.cloud.google.com/run
- Click service "wallstbots-backend"
- Click "Deploy New Revision"
- Image: lvl13tech/wallstbots:latest
- Click "Deploy"

### Add New Environment Variables to Backend

**1. Update Backend/.env file locally**

**2. Update Cloud Run:**
- Cloud Console → Cloud Run → wallstbots-backend
- Click "Edit and Deploy"
- Go to "Runtime settings"
- Add variables under "Runtime environment variables"
- Click "Deploy"

### Redirect Traffic from Old Domain to New

**If domain changes needed:**
1. Update API_BASE_URL in all frontend HTML files
2. Commit and push to GitHub
3. Cloudflare will auto-redeploy Pages projects
4. Update DNS if domain names changed

---

## Rollback Procedures

### Rollback Backend to Previous Version

```bash
# View Cloud Run revisions
gcloud run revisions list --service=wallstbots-backend --region=us-east1

# Deploy specific previous revision
gcloud run deploy wallstbots-backend --region=us-east1 \
  --image=gcr.io/project-id/wallstbots-backend:previous-tag
```

### Rollback Frontend Deployment

```bash
# In Cloudflare Pages:
# Deployments tab → Find previous deployment → Click "Rollback"
```

### Rollback Code in GitHub

```bash
# View commit history
git log --oneline

# Revert to specific commit
git revert <commit-hash>
git push origin master
```

---

## Performance Optimization Tips

1. **Frontend:**
   - Minimize HTTP requests (combine JS/CSS)
   - Lazy load bot cards (load on scroll)
   - Cache bot data locally (IndexedDB)

2. **Backend:**
   - Add database indexes for frequently queried fields
   - Implement caching (Redis) for bot performance data
   - Use connection pooling for database

3. **Cloudflare:**
   - Enable caching rules for static assets
   - Use Cloudflare Workers for edge logic
   - Enable compression for text responses

---

## Security Checklist

- [x] Credentials not in git (.env/.supabase.env excluded)
- [x] HTTPS enforced (Cloud Run & Cloudflare)
- [ ] CORS configured for production domains
- [ ] Rate limiting implemented on API
- [ ] Input validation on all endpoints
- [ ] SQL injection protection (ORM/parameterized queries)
- [ ] CSRF tokens if using forms
- [ ] Security headers configured
- [ ] Regular dependency updates
- [ ] API key rotation schedule

---

**End of Technical Reference**
