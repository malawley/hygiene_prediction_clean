#!/bin/bash
set -e

echo "=== 🛠 Building Trigger ==="
cd "$(dirname "$0")"

echo "--- Building Docker image (multi-stage)..."
docker build -t hygiene_prediction-trigger -f Dockerfile .

echo "✅ Docker image built: hygiene_prediction-trigger"
