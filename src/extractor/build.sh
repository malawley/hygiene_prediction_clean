#!/bin/bash
set -e

echo "=== 🛠 Building Extractor ==="

# Step 1: Ensure we're in extractor/, then move to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 2: Build Docker image using multi-stage Dockerfile
echo "--- Building Docker image (multi-stage)..."
docker build -t hygiene_prediction-extractor -f Dockerfile .

echo "✅ Docker image built: hygiene_prediction-extractor"
