# Backend Deploy Guide

## When to run this
Any time `Backend/main.py` changes. Run from Google Cloud Shell.

---

## 1. Run the DB migration (one-time, or if new tables were added)

Open Supabase → SQL Editor and run:

```
Backend/user_tracker_migration.sql
```

This creates: `user_tracker_data`, `user_stock_picks_history`, `paypal_webhook_log`

---

## 2. Set required environment variables in Cloud Run

Open Cloud Shell and run (replace placeholder values):

```bash
gcloud run services update wallstbots-backend \
  --region us-east1 \
  --update-env-vars \
SENDGRID_API_KEY=SG.xxxxxxxxxxxx,\
FROM_EMAIL=info@lvl13.tech,\
PAYPAL_CLIENT_ID=your_paypal_client_id,\
PAYPAL_CLIENT_SECRET=your_paypal_client_secret,\
PAYPAL_MODE=live,\
PAYPAL_PLAN_WALLSTBOTS=P-xxxxxxxxxxxxxxxx,\
PAYPAL_PLAN_BITBOT13=P-xxxxxxxxxxxxxxxx
```

> PAYPAL_PLAN_WALLSTBOTS and PAYPAL_PLAN_BITBOT13 are the PayPal Plan IDs for those
> two products. If missing, all subscriptions default to 'lvl13' platform.

---

## 3. Rebuild and redeploy the Docker image

```bash
# Clone or pull latest code
cd ~/wallstbots   # or wherever you keep it on Cloud Shell

# Copy the updated main.py up (if editing locally)
# Or just git pull if you pushed via push-backend.ps1

# Build and push the image
gcloud builds submit \
  --tag gcr.io/$(gcloud config get-value project)/wallstbots-backend \
  Backend/

# Deploy
gcloud run deploy wallstbots-backend \
  --image gcr.io/$(gcloud config get-value project)/wallstbots-backend \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated
```

---

## 4. Update the GCP VM nightly cron script

The VM runs `Project/scripts/refresh_data.py` each night. After pulling the updated
code, verify `secrets.json` has:

```json
{
  "tracker_data_dir": "/path/to/tracker/data",
  "api_url": "https://wallstbots-backend-868128114349.us-east1.run.app",
  "internal_api_key": "YOUR_INTERNAL_API_KEY",
  "platform": "lvl13"
}
```

The nightly cron entry (example):
```
0 6 * * 1-5 /usr/bin/python3 /home/user/wallstbots/Project/scripts/refresh_data.py >> /var/log/refresh_data.log 2>&1
```

---

## 5. Upload HostGator file

FTP into HostGator and upload:
- Local:  `Project/public_html/assets/app.js`
- Remote: `public_html/assets/app.js`

This updates the live lvl13.tech site immediately (no Cloudflare cache needed).

---

## 6. Configure PayPal webhook

In PayPal Developer Dashboard:
- Webhook URL: `https://wallstbots-backend-868128114349.us-east1.run.app/paypal/webhook`
- Events to subscribe:
  - `BILLING.SUBSCRIPTION.ACTIVATED`
  - `BILLING.SUBSCRIPTION.CANCELLED`
  - `BILLING.SUBSCRIPTION.PAYMENT.FAILED`
  - `PAYMENT.SALE.COMPLETED`
  - `PAYMENT.SALE.FAILED`

---

## Verification

After deploy, test these endpoints:

```bash
BASE=https://wallstbots-backend-868128114349.us-east1.run.app

# Public tracker (should return JSON)
curl $BASE/public/tracker/state | python3 -m json.tool | head -20

# Internal active users (replace YOUR_KEY)
curl -H "X-Internal-Key: YOUR_KEY" $BASE/internal/active-user-picks

# Health
curl $BASE/health
```
