#!/bin/bash
set -e

echo "=== 🏗️  Building Parquet Loader ==="
cd "$(dirname "$0")"

docker build -t loader-parquet .
echo "✅ Docker image built: loader-parquet"
