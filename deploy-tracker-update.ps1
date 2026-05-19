# deploy-tracker-update.ps1
# Phase 2B: Wire Tracker → Supabase
# Rebuilds backend with tracker endpoints, redeployes to Cloud Run,
# commits updated VM scripts to GitHub (VM will git pull on next cron run).
#
# Run from: C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\
# Prerequisites: docker, gcloud CLI authenticated, git

$ErrorActionPreference = "Stop"

$WORKSPACE  = "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots"
$BACKEND    = "$WORKSPACE\Backend"
$DOCKER_IMG = "lvl13/wallstbots:latest"
$SERVICE    = "wallstbots-backend"
$REGION     = "us-east1"

# ── Load .env so Cloud Run deploy picks up the new INTERNAL_API_KEY ───────────
Write-Host "`n=== Loading .env ===" -ForegroundColor Cyan
$envLines = Get-Content "$BACKEND\.env" | Where-Object { $_ -match '^\s*[^#]' -and $_ -match '=' }
foreach ($line in $envLines) {
    $k, $v = $line -split '=', 2
    [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
}
Write-Host "Loaded env vars (INTERNAL_API_KEY, SUPABASE_URL, DATABASE_URL...)" -ForegroundColor Green

# ── 1. Build Docker image ─────────────────────────────────────────────────────
Write-Host "`n=== Building Docker image ===" -ForegroundColor Cyan
Set-Location $BACKEND
docker build -t $DOCKER_IMG .
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
Write-Host "Build OK" -ForegroundColor Green

# ── 2. Push to Docker Hub ─────────────────────────────────────────────────────
Write-Host "`n=== Pushing to Docker Hub ===" -ForegroundColor Cyan
docker push $DOCKER_IMG
if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }
Write-Host "Push OK" -ForegroundColor Green

# ── 3. Deploy to Cloud Run (add INTERNAL_API_KEY to env) ─────────────────────
Write-Host "`n=== Deploying to Cloud Run ===" -ForegroundColor Cyan

$SUPABASE_URL              = $env:SUPABASE_URL
$SUPABASE_SERVICE_ROLE_KEY = $env:SUPABASE_SERVICE_ROLE_KEY
$SUPABASE_ANON_KEY         = $env:SUPABASE_ANON_KEY
$JWT_SECRET                = $env:JWT_SECRET
$DATABASE_URL              = $env:DATABASE_URL
$PAYPAL_CLIENT_ID          = $env:PAYPAL_CLIENT_ID
$PAYPAL_CLIENT_SECRET      = $env:PAYPAL_CLIENT_SECRET
$PAYPAL_MODE               = $env:PAYPAL_MODE
$INTERNAL_API_KEY          = $env:INTERNAL_API_KEY

gcloud run deploy $SERVICE `
  --image "docker.io/$DOCKER_IMG" `
  --platform managed `
  --region $REGION `
  --allow-unauthenticated `
  --set-env-vars="SUPABASE_URL=$SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY,SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY,JWT_SECRET=$JWT_SECRET,DATABASE_URL=$DATABASE_URL,PAYPAL_CLIENT_ID=$PAYPAL_CLIENT_ID,PAYPAL_CLIENT_SECRET=$PAYPAL_CLIENT_SECRET,PAYPAL_MODE=$PAYPAL_MODE,INTERNAL_API_KEY=$INTERNAL_API_KEY" `
  --memory 512Mi `
  --cpu 1 `
  --timeout 60 `
  --max-instances 100

if ($LASTEXITCODE -ne 0) { throw "Cloud Run deploy failed" }
Write-Host "Cloud Run deploy OK" -ForegroundColor Green

# ── 4. Smoke-test the new endpoints ───────────────────────────────────────────
Write-Host "`n=== Smoke tests ===" -ForegroundColor Cyan
$API = "https://wallstbots-backend-868128114349.us-east1.run.app"
Start-Sleep -Seconds 5

$h = Invoke-WebRequest -Uri "$API/health" -UseBasicParsing
Write-Host "/health → $($h.StatusCode)" -ForegroundColor Green

# Test internal push (expects 200 with the key, 403 without)
$pushBody = '{"data_type":"state","platform":"lvl13","data":{"test":true}}'
$pushResp = Invoke-WebRequest -Uri "$API/internal/tracker/push" `
    -Method POST `
    -Body $pushBody `
    -ContentType "application/json" `
    -Headers @{"X-Internal-Key" = $INTERNAL_API_KEY} `
    -UseBasicParsing
Write-Host "/internal/tracker/push → $($pushResp.StatusCode)" -ForegroundColor Green

# Test public read
$readResp = Invoke-WebRequest -Uri "$API/public/tracker/state?platform=lvl13" -UseBasicParsing
Write-Host "/public/tracker/state → $($readResp.StatusCode)" -ForegroundColor Green

# ── 5. Commit updated scripts + secrets to GitHub ─────────────────────────────
Write-Host "`n=== Committing to GitHub ===" -ForegroundColor Cyan
Set-Location $WORKSPACE
git add Backend/main.py `
        Project/scripts/refresh_data.py `
        Project/scripts/refresh_news.py `
        Backend/tracker_migration.sql

git commit -m "Phase 2B: Wire tracker → Supabase (dual-write)

- Backend/main.py: add POST /internal/tracker/push + GET /public/tracker/{type}
- refresh_data.py: push state/signals/reports to API after local write
- refresh_news.py: push news to API after local write
- tracker_migration.sql: tracker_live_data table schema
"
git push origin main

Write-Host "`n`n=============================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "=============================" -ForegroundColor Green
Write-Host ""
Write-Host "Next: SSH into GCP VM and run:" -ForegroundColor Yellow
Write-Host "  cd ~/wallstbots && git pull origin main" -ForegroundColor White
Write-Host ""
Write-Host "And run tracker_migration.sql in Supabase SQL Editor:" -ForegroundColor Yellow
Write-Host "  https://supabase.com/dashboard/project/rfsssoeyctobxbhpjyom/sql" -ForegroundColor White
Write-Host ""
