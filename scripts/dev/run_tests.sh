#!/bin/bash

# Run unit tests in Docker
# This script builds the Docker image and runs all tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "🧪 Running unit tests in Docker..."
echo "Building Docker image to ensure latest code..."

# Change to project root
cd "$PROJECT_ROOT"

# Build Docker image
echo "🔨 Building Docker image..."
docker build -f "$(pwd)/Dockerfile.python" -t shelly-tibber .

echo "🚀 Running tests..."
docker run --rm \
  -v "$(pwd)/tests:/app/tests" \
  -v "$(pwd)/src:/app/src" \
  -v "$(pwd)/output:/app/output" \
  shelly-tibber python -m pytest tests/ -v

echo "✅ Tests completed" 