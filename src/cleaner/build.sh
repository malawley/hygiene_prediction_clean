#!/bin/bash
set -e

echo "=== 🧼 Building Cleaner ==="

# Go to project root
cd "$(dirname "$0")/../.."

# Build Docker image from cleaner Dockerfile
docker build --no-cache -t cleaner -f src/cleaner/Dockerfile .

echo "✅ Docker image built: cleaner"
