@echo off
set PROJECT_ID=hygiene-prediction-434
set SERVICE_NAME=trigger
set REGION=us-central1
set IMAGE_NAME=gcr.io/%PROJECT_ID%/%SERVICE_NAME%

echo.
echo === Building Docker image ===
docker build -t %IMAGE_NAME% .

echo.
echo === Pushing image to Google Container Registry ===
docker push %IMAGE_NAME%

echo.
echo === Deploying to Cloud Run ===
gcloud run deploy %SERVICE_NAME% ^
  --image=%IMAGE_NAME% ^
  --platform=managed ^
  --region=%REGION% ^
  --allow-unauthenticated ^
  --set-env-vars=CLEANER_URL=https://your-cleaner-url/clean

echo.
echo ✅ Trigger service deployed!
