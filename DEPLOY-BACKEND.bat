@echo off
title DEPLOY BACKEND TO CLOUD RUN
cd /d "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Backend"

set LOG=%~dp0deploy-backend-result.txt
echo === DEPLOY BACKEND TO CLOUD RUN === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM ── Load .env if present ──────────────────────────────────────────
if exist ".env" (
  echo [env] Loading .env >> "%LOG%"
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
  )
)

REM ── Docker build ──────────────────────────────────────────────────
echo [1/4] Building Docker image... >> "%LOG%"
docker build -t wallstbots-backend:latest . >> "%LOG%" 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: docker build failed >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)
echo     OK >> "%LOG%"

REM ── Tag for Docker Hub ────────────────────────────────────────────
echo [2/4] Tagging image for Docker Hub... >> "%LOG%"
docker tag wallstbots-backend:latest lvl13/wallstbots-backend:latest >> "%LOG%" 2>&1
echo     OK >> "%LOG%"

REM ── Push to Docker Hub ────────────────────────────────────────────
echo [3/4] Pushing to Docker Hub... >> "%LOG%"
docker push lvl13/wallstbots-backend:latest >> "%LOG%" 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: docker push failed - are you logged in? Run: docker login >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)
echo     OK >> "%LOG%"

REM ── Deploy to Cloud Run ───────────────────────────────────────────
echo [4/4] Deploying to Cloud Run... >> "%LOG%"
gcloud run deploy wallstbots-backend ^
  --image docker.io/lvl13/wallstbots-backend:latest ^
  --platform managed ^
  --region us-east1 ^
  --project lvl13-tracker-496402 ^
  --allow-unauthenticated ^
  --set-env-vars="SUPABASE_URL=%SUPABASE_URL%,SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%,SUPABASE_ANON_KEY=%SUPABASE_ANON_KEY%,JWT_SECRET=%JWT_SECRET%,DATABASE_URL=%DATABASE_URL%,PAYPAL_CLIENT_ID=%PAYPAL_CLIENT_ID%,PAYPAL_CLIENT_SECRET=%PAYPAL_CLIENT_SECRET%,PAYPAL_MODE=sandbox,INTERNAL_API_KEY=%INTERNAL_API_KEY%" ^
  --memory 512Mi ^
  --cpu 1 ^
  --timeout 60 ^
  --max-instances 100 >> "%LOG%" 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: gcloud deploy failed >> "%LOG%"
  type "%LOG%" & pause & exit /b 1
)
echo     OK >> "%LOG%"

echo. >> "%LOG%"
echo === DONE === >> "%LOG%"
echo Backend is live at: https://wallstbots-backend-868128114349.us-east1.run.app >> "%LOG%"

type "%LOG%"
echo.
echo ============================================================
echo  Backend deployed to Cloud Run.
echo  URL: https://wallstbots-backend-868128114349.us-east1.run.app
echo ============================================================
pause
