#!/bin/bash
docker run --rm --name trigger \
  --network microservices-net \
  -p 8082:8080 \
  -v "$HOME/gcp-creds/service-account.json:/app/creds.json" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  trigger
