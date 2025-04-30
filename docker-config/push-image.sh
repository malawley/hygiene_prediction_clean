#!/bin/bash

# === push-image.sh ===
# Tag and push a local Docker image to Google Artifact Registry

# --- Configuration ---
PROJECT_ID="hygiene-prediction-434"
REGION="us-central1"
REPO="containers"

# --- Input Parameters ---
LOCAL_IMAGE="$1"       # e.g., hygiene_prediction-trigger
REMOTE_IMAGE="$2"      # e.g., trigger

# --- Validation ---
if [[ -z "$LOCAL_IMAGE" || -z "$REMOTE_IMAGE" ]]; then
  echo "Usage: ./push-image.sh <local-image> <remote-image-name>"
  echo "Example: ./push-image.sh hygiene_prediction-trigger trigger"
  exit 1
fi

# --- Authenticate with Artifact Registry ---
echo "🔐 Authenticating with Artifact Registry..."
gcloud auth print-access-token | \
  docker login -u oauth2accesstoken --password-stdin "https://${REGION}-docker.pkg.dev"

# --- Tag the Image ---
FULL_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${REMOTE_IMAGE}"
echo "🏷️  Tagging image: $LOCAL_IMAGE -> $FULL_TAG"
docker tag "$LOCAL_IMAGE" "$FULL_TAG"

# --- Push the Image ---
echo "📤 Pushing image to Artifact Registry..."
docker push "$FULL_TAG"
