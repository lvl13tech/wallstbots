# Deployment Guide: FastAPI Backend to GCP Cloud Run

**Status:** Phase 1 Foundation
**Date:** 2026-05-16

## Overview

The FastAPI backend runs on **GCP Cloud Run** — a serverless platform that:
- Auto-scales based on traffic
- Zero ops burden (no managing VMs)
- Integrates with GCP services
- Costs ~$20-50/month at typical traffic levels

## Prerequisites

1. GCP project: `lvl13-tracker-496402` (already exists)
2. gcloud CLI installed: `gcloud --version`
3. Docker installed: `docker --version`
4. Authenticated with GCP: `gcloud auth login`

## Step 1: Create Dockerfile

Create `Dockerfile` in the backend root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Step 2: Create .dockerignore

```
.env
.git
.gitignore
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.venv
venv
.DS_Store
```

## Step 3: Build Docker Image

```bash
cd Backend

# Build locally (optional, for testing)
docker build -t wallstbots-backend:latest .

# Test locally
docker run -p 8000:8000 --env-file .env wallstbots-backend:latest
# Visit http://localhost:8000/docs to see Swagger UI
```

## Step 4: Configure GCP

```bash
# Set project
gcloud config set project lvl13-tracker-496402

# Enable required APIs
gcloud services enable cloudrun.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable compute.googleapis.com
```

## Step 5: Create Cloud Run Service

### Option A: Deploy from Source (Easiest)

```bash
gcloud run deploy wallstbots-backend \
  --source . \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars="SUPABASE_URL=$SUPABASE_URL" \
  --set-env-vars="SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY" \
  --set-env-vars="JWT_SECRET=$JWT_SECRET" \
  --set-env-vars="DATABASE_URL=$DATABASE_URL" \
  --set-env-vars="PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID" \
  --set-env-vars="PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET" \
  --set-env-vars="PAYPAL_MODE=sandbox" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --max-instances 100
```

Replace `$SUPABASE_URL`, etc. with actual values.

### Option B: Push to Artifact Registry (Recommended for CI/CD)

```bash
# Create Artifact Registry
gcloud artifacts repositories create wallstbots \
  --repository-format docker \
  --location us-east1 \
  --description="Wall St. Bots Docker images"

# Configure Docker auth
gcloud auth configure-docker us-east1-docker.pkg.dev

# Build and push
docker build -t us-east1-docker.pkg.dev/lvl13-tracker-496402/wallstbots/backend:latest .
docker push us-east1-docker.pkg.dev/lvl13-tracker-496402/wallstbots/backend:latest

# Deploy
gcloud run deploy wallstbots-backend \
  --image us-east1-docker.pkg.dev/lvl13-tracker-496402/wallstbots/backend:latest \
  --platform managed \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars="SUPABASE_URL=..." \
  ... (rest of env vars)
```

## Step 6: Set Environment Variables

Instead of passing them on CLI, use Cloud Run Secrets:

```bash
# Store PayPal secret
echo -n "your_paypal_client_secret" | gcloud secrets create paypal-client-secret --data-file=-

# Reference in Cloud Run
gcloud run deploy wallstbots-backend \
  --update-secrets=PAYPAL_CLIENT_SECRET=paypal-client-secret:latest \
  ...
```

Or use a `.env.yaml` file:

```bash
gcloud run deploy wallstbots-backend \
  --source . \
  --platform managed \
  --region us-east1 \
  --env-vars-file=.env.yaml
```

Where `.env.yaml` is:
```yaml
SUPABASE_URL: https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY: xxxxx
JWT_SECRET: xxxxx
DATABASE_URL: postgresql://...
PAYPAL_CLIENT_ID: xxxxx
PAYPAL_CLIENT_SECRET: xxxxx
PAYPAL_MODE: sandbox
```

## Step 7: Verify Deployment

```bash
# Get service URL
gcloud run services describe wallstbots-backend --region us-east1

# Test health endpoint
curl https://wallstbots-backend-XXXXX.run.app/health

# View logs
gcloud run logs read wallstbots-backend --region us-east1 --limit 50

# Tail logs in real-time
gcloud alpha run logs stream wallstbots-backend --region us-east1
```

## Step 8: Configure Custom Domain

To use `api.wallstbots.tech` instead of `wallstbots-backend-XXXXX.run.app`:

```bash
# Add domain mapping
gcloud run domain-mappings create \
  --service=wallstbots-backend \
  --domain=api.wallstbots.tech \
  --region=us-east1

# Get DNS records
gcloud run domain-mappings describe api.wallstbots.tech --region us-east1
```

Then update your DNS provider (GoDaddy) to point `api.wallstbots.tech` to the CNAME provided.

## Step 9: Set Up Monitoring & Alerts

### View Metrics
```bash
# CPU usage
gcloud monitoring time-series list \
  --filter="metric.type=run.googleapis.com/request_count"

# Error rate
gcloud monitoring time-series list \
  --filter="metric.type=run.googleapis.com/request_latencies"
```

### Create Alert Policy (Cloud Console)
1. Go to **Cloud Monitoring > Alerting**
2. Click **Create Policy**
3. Set condition: Error rate > 1% or Latency p95 > 2s
4. Send notification to email

## Step 10: Enable Cloud Logging

Logs are automatically sent to Cloud Logging. View them:

```bash
# Python exceptions
gcloud logs read "resource.type=cloud_run_revision" --limit 100

# Filter by service
gcloud logs read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=wallstbots-backend" \
  --limit 50
```

## Step 11: Scaling & Performance

### Auto-Scaling Config
```bash
gcloud run services update wallstbots-backend \
  --max-instances 100 \
  --min-instances 1 \
  --region us-east1
```

### Memory & CPU
```bash
# Increase if needed
gcloud run services update wallstbots-backend \
  --memory 1Gi \
  --cpu 2 \
  --region us-east1
```

## Step 12: Database Connection Pooling

Cloud Run instances may create many connections to Postgres. Use **PgBouncer** connection pooling (already enabled in Supabase setup):

```python
# In main.py, use the pooling URL:
DATABASE_URL = "postgresql://pooling_user:password@YOUR_PROJECT.supabase.co:6543/postgres"
```

This reduces connection overhead from 100+ Cloud Run instances to a manageable pool.

## Troubleshooting

### "Permission denied" when deploying
```bash
gcloud auth application-default login
gcloud config set project lvl13-tracker-496402
```

### Container won't start
```bash
# Build locally to test
docker build -t test .
docker run -e DATABASE_URL="..." -p 8000:8000 test

# Check logs
gcloud run logs read wallstbots-backend --limit 100
```

### Database connection timeout
→ Ensure `DATABASE_URL` uses the pooling endpoint (port 6543), not the direct endpoint (5432).

### Deployment takes forever
→ Cloud Build can be slow. Use `gcloud run deploy --source .` for quick deployments, or push to Artifact Registry for production.

## Success Criteria

✅ `gcloud run services list` shows `wallstbots-backend`  
✅ `curl https://wallstbots-backend-....run.app/health` returns `{"status": "healthy"}`  
✅ Logs show no errors  
✅ Domain `api.wallstbots.tech` resolves to the Cloud Run service  
✅ Frontend can call endpoints and get 200 responses  

Once all ✅, the backend is ready for integration with frontends.
