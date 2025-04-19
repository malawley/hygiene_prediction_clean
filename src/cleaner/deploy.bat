@echo off
set PROJECT_ID=hygiene-prediction
set SERVICE_NAME=cleaner
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
  --set-env-vars=RUN_MODE=cloud,BUCKET_NAME=raw-inspection-data,RAW_PREFIX=raw-data,CLEAN_PREFIX=clean-data,CLEAN_ROW_BUCKET_NAME=cleaned-inspection-data-row,CLEAN_COL_BUCKET_NAME=cleaned-inspection-data-column

echo.
echo ✅ Deployment complete!
