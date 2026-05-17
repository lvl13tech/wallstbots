@echo off
REM Deploy Wall St. Bots Backend to Cloud Run
cd "C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. Wall St Bots\Backend"

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
  --set-env-vars="SUPABASE_URL=%SUPABASE_URL%,SUPABASE_SERVICE_ROLE_KEY=%SUPABASE_SERVICE_ROLE_KEY%,SUPABASE_ANON_KEY=%SUPABASE_ANON_KEY%,JWT_SECRET=%JWT_SECRET%,DATABASE_URL=%DATABASE_URL%,PAYPAL_CLIENT_ID=%PAYPAL_CLIENT_ID%,PAYPAL_CLIENT_SECRET=%PAYPAL_CLIENT_SECRET%,PAYPAL_MODE=sandbox" ^
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
echo Updating Frontend API URLs...
echo ================================
cd "C:\Users\temps\OneDrive\Desktop\Claude\Websites\1. Wall St Bots"
python update-frontend-api-urls.py "%SERVICE_URL%"

echo.
echo ================================
echo Committing and Pushing to GitHub...
echo ================================
git add .
git commit -m "Update frontend API URLs to Cloud Run service: %SERVICE_URL%"
git push origin main

echo.
echo ================================
echo DEPLOYMENT COMPLETE!
echo ================================
echo Service URL: %SERVICE_URL%
echo.
pause
