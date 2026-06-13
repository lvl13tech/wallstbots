@echo off
REM Deploy Wall St. Bots Backend to Cloud Run
cd "C:\Users\temps\OneDrive\Desktop\Claude\Websites\WallStBots\Backend"

echo ================================
echo Building Docker image...
echo ================================
docker build -t wallstbots-backend:latest .

echo.
echo ================================
echo Tagging image for Docker Hub...
echo ================================
docker tag wallstbots-backend:latest lvl13/wallstbots-backend:latest

echo.
echo ================================
echo Pushing to Docker Hub...
echo ================================
docker push lvl13/wallstbots-backend:latest

echo.
echo ================================
echo Deploying to Cloud Run...
echo ================================
gcloud run deploy wallstbots-backend ^
  --image docker.io/lvl13/wallstbots-backend:latest ^
  --platform managed ^
  --region us-east1 ^
  --allow-unauthenticated ^
  --set-env-vars="SUPABASE_URL=%SUPABASE_URL%,SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%,SUPABASE_ANON_KEY=%SUPABASE_ANON_KEY%,JWT_SECRET=%JWT_SECRET%,DATABASE_URL=%DATABASE_URL%,STRIPE_SECRET_KEY=%STRIPE_SECRET_KEY%,STRIPE_WEBHOOK_SECRET=%STRIPE_WEBHOOK_SECRET%,RESEND_API_KEY=%RESEND_API_KEY%,POLYGON_API_KEY=%POLYGON_API_KEY%" ^
  --memory 512Mi ^
  --cpu 1 ^
  --timeout 60 ^
  --max-instances 100

echo.
echo ================================
echo Getting Service URL...
echo ================================
for /f "tokens=*" %%i in ('gcloud run services describe wallstbots-backend --region us-east1 --format="value(status.url)"') do set SERVICE_URL=%%i
echo Service URL: %SERVICE_URL%

echo.
echo ================================
echo Testing health endpoint...
echo ================================
timeout /t 5 /nobreak
curl "%SERVICE_URL%/health"

echo.
echo ================================
echo DEPLOYMENT COMPLETE!
echo ================================
echo Service URL: %SERVICE_URL%
echo.
pause
