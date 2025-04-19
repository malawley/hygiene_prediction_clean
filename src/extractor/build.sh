#!/bin/bash
set -e

echo "=== 🛠 Building Extractor ==="

# Step 1: Ensure we're in extractor/, then move to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Step 2: Compile Go binary using local go.mod
echo "--- Compiling Go code..."
GOOS=linux GOARCH=amd64 go build -o build/extractor ./cmd/extractor.go
echo "✅ Go build successful: build/extractor"

# Step 3: Build Docker image from current dir
echo "--- Building Docker image..."
docker build -t extractor .

echo "✅ Docker image built: extractor"
