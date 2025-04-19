#!/bin/bash
docker run --rm --name trigger \
  --network microservices-net \
  -p 8082:8080 \
  -e HTTP_MODE=true \
  -e SERVICE_CONFIG_PATH=/app/services.json \
  -v "$PWD/src/configure/services.json:/app/services.json" \
  trigger
