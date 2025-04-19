#!/bin/bash
set -e

echo "=== 🛠 Building Trigger ==="

# Step 1: Compile Go binary for Linux
echo "--- Compiling Go code..."
GOOS=linux GOARCH=amd64 go build -o build/trigger ./cmd/trigger.go
echo "✅ Go build successful: build/trigger"

# Step 2: Build Docker image from src/ context
echo "--- Building Docker image..."
docker build -f trigger/Dockerfile -t trigger .

echo "✅ Docker image built: trigger"

