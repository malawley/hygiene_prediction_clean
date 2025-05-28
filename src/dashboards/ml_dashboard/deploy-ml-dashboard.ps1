# Set strict mode and fail fast
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Define image and service info
$IMAGE_NAME = "hygiene-dashboard"
$GCP_PROJECT = "hygiene-prediction-434"
$REGION = "us-central1"
$SERVICE_NAME = "ml-dashboard"
$REPO = "$REGION-docker.pkg.dev/$GCP_PROJECT/containers/$SERVICE_NAME"

Write-Host "Building Docker image..."
docker build -t $IMAGE_NAME .

Write-Host "Tagging image for Artifact Registry..."
docker tag $IMAGE_NAME $REPO

Write-Host "Authenticating Docker to Artifact Registry..."
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://$REGION-docker.pkg.dev

Write-Host "Pushing image to Artifact Registry..."
docker push $REPO

Write-Host "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME `
  --image=$REPO `
  --platform=managed `
  --region=$REGION `
  --port=8501 `
  --allow-unauthenticated `
  --memory=2Gi `
  --timeout=300

Write-Host "Fetching service URL..."
$URL = gcloud run services describe $SERVICE_NAME `
  --platform=managed `
  --region=$REGION `
  --format='value(status.url)'

Write-Host "Opening: $URL"
Start-Process $URL
