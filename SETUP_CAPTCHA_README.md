# Captcha (Cloudflare Turnstile) — Setup Guide

Stops bot/spam signups at the door. Two keys are needed (free, from Cloudflare).
The code is already in place; you just create the keys and run one deploy.

## Step 1 — Create the Turnstile widget (2 min)
1. Go to **dash.cloudflare.com → Turnstile** (left sidebar) → **Add widget**.
2. Name it (e.g. "WallStBots signup").
3. **Hostnames:** add `wallstbots.tech`, `aistocks.tech`, `bitbot13.tech`
   (and `localhost` if you test locally).
4. Widget type: **Managed** (recommended).
5. Create. Cloudflare shows you TWO keys:
   - **Site Key** (public — goes in the website code)
   - **Secret Key** (private — goes in the backend)

## Step 2 — Put the SECRET key in the backend (Cloud Run env var)
The backend reads `TURNSTILE_SECRET_KEY`. Add it wherever the other backend secrets
live (Cloud Run service → Variables, or your deploy config that sets SUPABASE_* etc.):
```
TURNSTILE_SECRET_KEY = <your Turnstile Secret Key>
```
**Until this is set, captcha is SKIPPED (signups still work) — so nothing breaks.**
Once set, the backend enforces the captcha.

## Step 3 — Put the SITE key in the website + deploy
Double-click **DEPLOY-captcha_2026-06-29.bat**. It will:
- prompt you to paste the **Site Key**,
- write it into all 3 sites' signup forms,
- commit + push (Cloudflare auto-deploys the sites; backend already has the code).

## How it behaves
- The signup form shows the Turnstile checkbox; the token is sent to the backend.
- Backend `/auth/signup-free` (and `/auth/signup`) verify the token with Cloudflare
  before creating the account. Bots that can't solve it are rejected.
- **Graceful:** if either key is missing, signups still work (captcha just isn't
  enforced yet) — so you can deploy the site key and add the secret in any order
  without an outage.

## Layered with what's already live
- Email-confirmation gate: bot accounts can't receive member emails.
- This captcha: bots can't create accounts in the first place.
- Together they close the signup-abuse hole that let the 3 spam accounts in.
