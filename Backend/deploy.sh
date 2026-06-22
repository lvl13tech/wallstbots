#!/bin/bash
set -e

# Wall St. Bots FastAPI Backend — Cloud Shell Deployment Script
# Run this inside Google Cloud Shell

PROJECT_ID="lvl13-tracker-496402"
REGION="us-east1"
SERVICE_NAME="wallstbots-backend"

echo "================================"
echo "Deploying $SERVICE_NAME to Cloud Run"
echo "Project: $PROJECT_ID | Region: $REGION"
echo "================================"

gcloud config set project $PROJECT_ID

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✓ Loaded .env file"
else
    echo "✗ No .env file found in $SCRIPT_DIR"
    echo "  Create one with your secrets before deploying (see .env.example)"
    exit 1
fi

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="SUPABASE_URL=$SUPABASE_URL" \
  --set-env-vars="SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY" \
  --set-env-vars="SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY" \
  --set-env-vars="JWT_SECRET=$JWT_SECRET" \
  --set-env-vars="DATABASE_URL=$DATABASE_URL" \
  --set-env-vars="STRIPE_SECRET_KEY=$STRIPE_SECRET_KEY" \
  --set-env-vars="STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK_SECRET" \
  --set-env-vars="RESEND_API_KEY=$RESEND_API_KEY" \
  --set-env-vars="POLYGON_API_KEY=$POLYGON_API_KEY" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --max-instances 20

echo ""
echo "================================"
echo "✓ Deployment complete!"
echo "================================"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "Live URL: $SERVICE_URL"
echo ""
echo "Health check:"
curl -s "$SERVICE_URL/health"
echo ""
echo "To view logs: gcloud run logs read $SERVICE_NAME --region $REGION --limit 50"
