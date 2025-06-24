#!/bin/bash

# Run unit tests in Docker
# This script builds the Docker image and runs all tests

set -e

echo "🧪 Running unit tests in Docker..."
echo "Building Docker image to ensure latest code..."

# Build Docker image
echo "🔨 Building Docker image..."
docker build -f Dockerfile.python -t shelly-tibber .

echo "🚀 Running tests..."
docker run --rm \
  -v "$PROJECT_DIR/tests:/app/tests" \
  -v "$PROJECT_DIR/src:/app/src" \
  -v "$PROJECT_DIR/output:/app/output" \
  shelly-tibber python -m pytest tests/ -v

echo "✅ Tests completed" 