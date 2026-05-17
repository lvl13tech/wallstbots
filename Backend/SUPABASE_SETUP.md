# Supabase Setup for Wall St. Bots

**Status:** Phase 1 Foundation Setup
**Date:** 2026-05-16

## Overview

Supabase is a managed Postgres database with built-in auth, realtime, and a REST API. We're using it for:
- **Postgres database** — all tables defined in `schema.sql`
- **Supabase Auth** — email/password authentication with JWT tokens
- **Automatic REST API** — Supabase generates REST endpoints for every table
- **Row-Level Security (RLS)** — users can only see their own data

## Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in (use lvl13cs@gmail.com)
2. Click **New Project**
3. **Project name:** `wallstbots-prod`
4. **Database password:** Use a strong random password (save to 1password)
5. **Region:** `us-east1` (same region as your GCP VM for low latency)
6. Click **Create new project** (takes 3-5 minutes)

## Step 2: Load the Schema

Once the project is ready:

1. In Supabase dashboard, go to **SQL Editor** (left sidebar)
2. Click **New Query**
3. Copy the entire contents of `schema.sql` into the editor
4. Click **Run**

This creates:
- All tables (users, bots, subscriptions, promo_codes, etc.)
- All indexes (for performance)
- Row-level security (RLS) policies
- Triggers (auto-timestamps, referral code generation)
- Views (for reporting)
- Initial promo codes (levelUp13, KING13)

## Step 3: Configure Supabase Auth

Supabase Auth uses the `auth.users` table automatically. We link our `users` table to it via UUID foreign key.

### Email Templates (Supabase Dashboard > Authentication > Email Templates)

1. **Confirm signup email** — customize if needed (default is fine)
2. **Confirm email change** — customize if needed
3. **Reset password** — customize if needed
4. **Magic link** — we're using email/password, so this can stay default

### Auth Providers

We're using email/password only. No OAuth yet (can add later).

## Step 4: Get API Keys

In Supabase dashboard, go to **Settings > API**. You'll see:

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbG...  # public key, used by frontend
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...  # private key, used by backend only
```

Save these to your environment:

### For FastAPI Backend (`.env`)
```
DATABASE_URL=postgresql://postgres:PASSWORD@xxxxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbG...
JWT_SECRET=xxxxx  # from Supabase Settings > API > JWT Secret
```

### For Frontend (JavaScript)
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://xxxxx.supabase.co',
  'YOUR_ANON_KEY'  // NOT the service_role_key
)
```

## Step 5: Test Auth Flow

### Signup (Frontend)
```javascript
const { user, session, error } = await supabase.auth.signUp({
  email: 'test@example.com',
  password: 'SecurePassword123!'
})
// session.access_token = JWT to use in API calls
```

### Login (Frontend)
```javascript
const { user, session, error } = await supabase.auth.signInWithPassword({
  email: 'test@example.com',
  password: 'SecurePassword123!'
})
// Use session.access_token for subsequent API calls
```

### Verify with Database

In Supabase **SQL Editor**, run:
```sql
SELECT id, email, created_at FROM auth.users;
SELECT id, email, role, referral_code FROM users;
```

Both should show the new user.

## Step 6: Environment Variables for FastAPI

Create `.env` in backend root:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_PROJECT.supabase.co:5432/postgres
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
JWT_SECRET=YOUR_JWT_SECRET

# PayPal
PAYPAL_CLIENT_ID=xxxxx
PAYPAL_CLIENT_SECRET=xxxxx
PAYPAL_MODE=sandbox  # or 'live'

# Email (for password resets)
SENDGRID_API_KEY=xxxxx

# GCP (for Cloud Run deployment later)
GCP_PROJECT_ID=lvl13-tracker-496402
```

## Step 7: Connection Pooling (Important for Reliability)

Supabase Postgres has a connection limit. For production, enable **pgBouncer** connection pooling:

1. In Supabase dashboard, go to **Database > Connection Pooling**
2. Enable it (set mode to `Transaction` for best compatibility)
3. Get the **Pooling URL** (different from the direct Postgres URL)
4. Use the pooling URL in `DATABASE_URL` in FastAPI `.env`

## Step 8: Backups & Recovery

Supabase automatically backs up daily. You can:
1. **View backups** in Supabase dashboard: **Settings > Backups**
2. **Point-in-time recovery** is available for 7 days
3. **Automated backups** keep last 7 days

For safety, also dump the schema regularly:

```bash
pg_dump \
  postgresql://postgres:PASSWORD@YOUR_PROJECT.supabase.co:5432/postgres \
  --schema-only > schema_backup.sql

pg_dump \
  postgresql://postgres:PASSWORD@YOUR_PROJECT.supabase.co:5432/postgres \
  > full_backup.sql  # includes data, ~500MB+
```

Save backups to GCS:
```bash
gsutil cp schema_backup.sql gs://wallstbots-backups/
```

## Step 9: Monitoring & Alerts

In Supabase dashboard, go to **Database > Monitoring**:

- **Connection count** — alert if > 80
- **Cache hit ratio** — should be > 95%
- **Query performance** — slow queries logged
- **Storage size** — alert if > 90% of plan limit

Set up email alerts in Supabase: **Notifications > Email Alerts**

## Step 10: Row-Level Security (RLS) Verification

RLS is defined in `schema.sql`. Verify it's working:

**As authenticated user 1:**
```sql
-- Should return only their own bots
SELECT id, name FROM bots WHERE user_id = auth.uid();
```

**As authenticated user 2 (different email):**
```sql
-- Should return zero rows (can't see user 1's bots)
SELECT id, name FROM bots WHERE user_id = '<user1_id>';
```

If RLS is working correctly, user 2 gets zero rows.

## Step 11: API Endpoints (Auto-Generated by Supabase)

Once schema is loaded, Supabase automatically creates REST endpoints:

**Get all bots for current user:**
```bash
curl https://xxxxx.supabase.co/rest/v1/bots \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "apikey: YOUR_ANON_KEY"
```

**Create a bot:**
```bash
curl https://xxxxx.supabase.co/rest/v1/bots \
  -X POST \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"platform":"lvl13","name":"My Bot"}'
```

These endpoints respect RLS — the `Authorization: Bearer JWT` token tells Supabase who the user is.

## Troubleshooting

### "Column does not exist" error
→ Schema didn't load properly. Check SQL Editor for errors and re-run `schema.sql`.

### RLS blocking legitimate queries
→ Check Supabase **Settings > Database > RLS** to see which policies are enabled.
→ Temporarily disable RLS to test (re-enable in production).

### JWT token expired
→ Frontend should refresh using `supabase.auth.refreshSession()`

### Too many connections
→ Use the pooling URL, not the direct Postgres URL.

---

## Success Criteria

✅ Supabase project created  
✅ `schema.sql` loaded without errors  
✅ Auth users table synced  
✅ RLS policies working (users can only see their own data)  
✅ Database and API keys in `.env`  
✅ FastAPI backend can connect and read/write data  

Once all are ✅, move to **Task #2: Build FastAPI backend**.
