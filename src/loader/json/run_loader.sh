#!/bin/bash
docker run --rm --name loader-json \
  --network microservices-net \
  -p 8084:8080 \
  -v "$HOME/gcp-creds/service-account.json:/app/creds.json" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  loader-json
