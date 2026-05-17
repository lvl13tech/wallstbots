#!/bin/bash
set -e

# Wall St. Bots FastAPI Backend - GCP Cloud Run Deployment Script
# Paste this entire script into Cloud Shell and run it

PROJECT_ID="lvl13-tracker-496402"
REGION="us-east1"
SERVICE_NAME="wallstbots-backend"

echo "================================"
echo "Deploying $SERVICE_NAME to Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "================================"

# Set project
gcloud config set project $PROJECT_ID
echo "✓ Project configured"

# Attempt to enable APIs (will fail if org policy blocks it)
echo "Attempting to enable required APIs..."
gcloud services enable run.googleapis.com || echo "⚠ Cloud Run API - enable manually in GCP Console"
gcloud services enable compute.googleapis.com || echo "⚠ Compute Engine API - enable manually in GCP Console"
gcloud services enable artifactregistry.googleapis.com || echo "⚠ Artifact Registry API - enable manually in GCP Console"

# Try deployment with source (Option A - Easiest, auto-enables if possible)
echo ""
echo "Attempting deployment from source..."
echo "(This may automatically enable required APIs)"
echo ""

# Get env variables from .env file
cd "$(dirname "$0")"
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✓ Loaded .env variables"
else
    echo "✗ .env file not found!"
    exit 1
fi

# Deploy
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
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

echo ""
echo "================================"
echo "✓ Deployment successful!"
echo "================================"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo ""
echo "Service URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Test health: curl $SERVICE_URL/health"
echo "2. View logs: gcloud run logs read $SERVICE_NAME --region $REGION --limit 50"
echo "3. Set up custom domain (api.wallstbots.tech) if needed"
