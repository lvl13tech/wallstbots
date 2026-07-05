@echo off
title DEPLOY BACKEND TO CLOUD RUN
cd /d "%~dp0Backend"

set LOG=%~dp0deploy-backend-result.txt
echo === DEPLOY BACKEND TO CLOUD RUN === > "%LOG%"
echo %DATE% %TIME% >> "%LOG%"
echo. >> "%LOG%"

REM ── Load .env if present ──────────────────────────────────────────
REM NOTE: previously this used a cmd.exe "for /f + setlocal enabledelayedexpansion"
REM parser to read .env. That parser corrupts any value containing a literal "!"
REM (cmd.exe treats "!...!" as a variable reference) -- this silently mangled
REM DATABASE_URL's password (WsbProd2024!Zx9k) and broke the DB connection after
REM deploy, with no error until Cloud Run's container failed to start. Loading
REM .env via PowerShell instead avoids cmd.exe's quoting/expansion pitfalls
REM entirely -- it treats every line as a literal string.
if exist ".env" (
  echo [env] Loading .env >> "%LOG%"
  for /f "usebackq tokens=1,* delims==" %%A in (`powershell -NoProfile -Command "Get-Content '.env' | Where-Object { $_ -match '=' -and $_ -notmatch '^\s*#' } | ForEach-Object { $_ }"`) do (
    set "%%A=%%B"
  )
)
set "SUPABASE_URL=%SUPABASE_URL%" & set "SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%" & set "SUPABASE_ANON_KEY=%SUPABASE_ANON_KEY%" & set "JWT_SECRET=%JWT_SECRET%" & set "DATABASE_URL=%DATABASE_URL%" & set "INTERNAL_API_KEY=%INTERNAL_API_KEY%" & set "STRIPE_SECRET_KEY=%STRIPE_SECRET_KEY%" & set "STRIPE_WEBHOOK_SECRET=%STRIPE_WEBHOOK_SECRET%" & set "RESEND_API_KEY=%RESEND_API_KEY%"

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
  --set-env-vars="SUPABASE_URL=%SUPABASE_URL%,SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%,SUPABASE_ANON_KEY=%SUPABASE_ANON_KEY%,JWT_SECRET=%JWT_SECRET%,DATABASE_URL=%DATABASE_URL%,INTERNAL_API_KEY=%INTERNAL_API_KEY%,STRIPE_SECRET_KEY=%STRIPE_SECRET_KEY%,STRIPE_WEBHOOK_SECRET=%STRIPE_WEBHOOK_SECRET%,RESEND_API_KEY=%RESEND_API_KEY%" ^
  --memory 512Mi ^
  --cpu 1 ^
  --timeout 60 ^
  --max-instances 20 >> "%LOG%" 2>&1
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
