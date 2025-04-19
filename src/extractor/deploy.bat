@echo off
set PROJECT_ID=hygiene-prediction
set SERVICE_NAME=extractor
set IMAGE_NAME=gcr.io/%PROJECT_ID%/%SERVICE_NAME%

echo Building Docker image...
docker build -t %IMAGE_NAME% .

echo Pushing image to Google Container Registry...
docker push %IMAGE_NAME%

echo Deploying to Cloud Run...
gcloud run deploy %SERVICE_NAME% ^
  --image=%IMAGE_NAME% ^
  --platform=managed ^
  --region=us-central1 ^
  --allow-unauthenticated ^
  --set-env-vars=HTTP_MODE=true,CLOUD_RUN_ENV=true,BUCKET_NAME=raw-inspection-data,CLEANER_URL=https://cleaner-service-url/clean
