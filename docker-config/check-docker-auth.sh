#!/bin/bash

REGISTRY="us-central1-docker.pkg.dev"
EXPECTED_HELPER="gcloud"

echo "🔍 Checking Docker auth config for: $REGISTRY"

CONFIG_FILE="$HOME/.docker/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "❌ Docker config file not found at $CONFIG_FILE"
  echo "🔧 Run: gcloud auth configure-docker $REGISTRY"
  exit 1
fi

helper=$(jq -r ".credHelpers[\"$REGISTRY\"]" "$CONFIG_FILE" 2>/dev/null)

if [ "$helper" == "$EXPECTED_HELPER" ]; then
  echo "✅ Docker is configured to use '$EXPECTED_HELPER' helper for $REGISTRY"
  exit 0
else
  echo "❌ Docker not configured correctly for $REGISTRY"
  echo "🔧 Run: gcloud auth configure-docker $REGISTRY"
  exit 2
fi
