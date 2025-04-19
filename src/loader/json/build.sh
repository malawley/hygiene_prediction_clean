#!/bin/bash
set -e

echo "=== 🏗️  Building JSON Loader ==="
cd "$(dirname "$0")"

docker build -t loader-json .
echo "✅ Docker image built: loader-json"
