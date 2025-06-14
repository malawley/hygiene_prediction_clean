#!/bin/bash
docker run --rm --name extractor \
  --network microservices-net \
  -p 8081:8080 \
  -e HTTP_MODE=true \
  -e SERVICE_CONFIG_PATH=/services.json \
  -e BUCKET_NAME=raw-inspection-data-434 \
  -v "$HOME/gcp-creds/service-account.json:/app/creds.json" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  extractor
