# Wall St. Bots - Deploy Backend to Cloud Run and Update Frontends
# This script rebuilds the Docker image with the updated PORT env var handling,
# pushes it to Docker Hub, and deploys to Cloud Run

$ErrorActionPreference = "Stop"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Rebuilding Docker Image (with updated PORT env var)" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to Backend directory
Set-Location "C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. Wall St Bots\Backend"

# Build the image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t wallstbots-backend:latest .

Write-Host ""
Write-Host "Tagging image for Docker Hub..." -ForegroundColor Yellow
docker tag wallstbots-backend:latest lvl13/wallstbots-backend:latest

Write-Host ""
Write-Host "Pushing to Docker Hub..." -ForegroundColor Yellow
docker push lvl13/wallstbots-backend:latest

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Deploying to Cloud Run" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Deploy to Cloud Run
Write-Host "Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy wallstbots-backend `
  --image docker.io/lvl13/wallstbots-backend:latest `
  --platform managed `
  --region us-east1 `
  --allow-unauthenticated `
  --set-env-vars="SUPABASE_URL=$env:SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY=$env:SUPABASE_SERVICE_ROLE_KEY,SUPABASE_ANON_KEY=$env:SUPABASE_ANON_KEY,JWT_SECRET=$env:JWT_SECRET,DATABASE_URL=$env:DATABASE_URL,PAYPAL_CLIENT_ID=$env:PAYPAL_CLIENT_ID,PAYPAL_CLIENT_SECRET=$env:PAYPAL_CLIENT_SECRET,PAYPAL_MODE=sandbox" `
  --memory 512Mi `
  --cpu 1 `
  --timeout 60 `
  --max-instances 100

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Getting Service URL" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

$SERVICE_URL = gcloud run services describe wallstbots-backend --region us-east1 --format='value(status.url)'
Write-Host "Service URL: $SERVICE_URL" -ForegroundColor Green

# Save to temp file for next step
$SERVICE_URL | Out-File "C:\temp\cloud-run-url.txt" -Force

Write-Host ""
Write-Host "Waiting for service to stabilize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Testing health endpoint..." -ForegroundColor Yellow
$healthCheck = Invoke-WebRequest -Uri "$SERVICE_URL/health" -UseBasicParsing
Write-Host "Health check: $($healthCheck.StatusCode)" -ForegroundColor Green
Write-Host $healthCheck.Content

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Updating Frontend API URLs" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Run the update-frontend-api-urls.py script
Write-Host "Updating frontends to use Cloud Run URL..." -ForegroundColor Yellow
Set-Location "C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. Wall St Bots"
python update-frontend-api-urls.py "$SERVICE_URL"

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Committing and Pushing to GitHub" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Commit changes
Write-Host "Committing changes..." -ForegroundColor Yellow
git add .
git commit -m "Update frontend API URLs to Cloud Run service: $SERVICE_URL"

Write-Host ""
Write-Host "Pushing to GitHub (triggers Cloudflare Pages)..." -ForegroundColor Yellow
git push origin main

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "✓ DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "API URL: $SERVICE_URL" -ForegroundColor Green
Write-Host ""
Write-Host "Frontends will be live in 1-2 minutes:"
Write-Host "  - https://lvl13.tech"
Write-Host "  - https://bitbot13.tech"
Write-Host "  - https://wallstbots.tech"
Write-Host ""
Write-Host "Monitor backend logs with:"
Write-Host "  gcloud run logs read wallstbots-backend --region us-east1 --limit 50"
