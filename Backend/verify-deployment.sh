#!/bin/bash

# Wall St. Bots FastAPI Backend - Deployment Verification Script
# Paste this into Cloud Shell to verify the deployment was successful

PROJECT_ID="lvl13-tracker-496402"
REGION="us-east1"
SERVICE_NAME="wallstbots-backend"

echo "================================"
echo "VERIFYING CLOUD RUN DEPLOYMENT"
echo "================================"
echo ""

# Check if service exists
echo "1. Checking if Cloud Run service exists..."
if gcloud run services describe $SERVICE_NAME --region $REGION &>/dev/null; then
    echo "   ✓ Service found: $SERVICE_NAME"
else
    echo "   ✗ Service NOT found"
    echo ""
    echo "Listing all services in the project:"
    gcloud run services list --region $REGION
    exit 1
fi

echo ""
echo "2. Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "   Service URL: $SERVICE_URL"

echo ""
echo "3. Testing health endpoint..."
if command -v curl &> /dev/null; then
    HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health")
    if [ "$HEALTH_CHECK" == "200" ]; then
        echo "   ✓ Health check passed (HTTP 200)"
        echo "   Response: $(curl -s "$SERVICE_URL/health")"
    else
        echo "   ✗ Health check failed (HTTP $HEALTH_CHECK)"
        echo "   This may be normal if the service is still starting up."
        echo "   Wait a few moments and try again."
    fi
else
    echo "   (curl not available in Cloud Shell)"
    echo "   You can test the endpoint manually in your browser:"
    echo "   $SERVICE_URL/health"
fi

echo ""
echo "4. Checking deployment status..."
REPLICAS=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.conditions[0].message)')
echo "   Status: $REPLICAS"

echo ""
echo "5. Recent logs (last 20 lines)..."
gcloud run logs read $SERVICE_NAME --region $REGION --limit 20

echo ""
echo "================================"
echo "DEPLOYMENT VERIFICATION COMPLETE"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Test the API endpoints (Swagger UI available at $SERVICE_URL/docs)"
echo "2. Update frontend .env files with the service URL"
echo "3. Set up custom domain (api.wallstbots.tech) if needed"
echo "4. Configure environment variables securely using Google Cloud Secrets"
echo ""
echo "Monitor logs in real-time with:"
echo "gcloud alpha run logs stream $SERVICE_NAME --region $REGION"
