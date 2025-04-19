#!/bin/bash
set -e

echo "=== 🛠 Building Trigger ==="

# Step 1: Build in module root (src/trigger)
cd "$(dirname "$0")"

# Step 2: Compile Go binary
echo "--- Compiling Go code..."
GOOS=linux GOARCH=amd64 go build -o build/trigger ./cmd/trigger.go
echo "✅ Go build successful: build/trigger"

# Step 3: Build Docker image from current dir
echo "--- Building Docker image..."
docker build -t trigger .

echo "✅ Docker image built: trigger"
