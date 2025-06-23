#!/bin/bash

# Run unit tests in Docker
# This script builds the Docker image and runs all tests

set -e

echo "🧪 Running unit tests in Docker..."
echo "Building Docker image to ensure latest code..."

# Build the Docker image
docker build -f Dockerfile.python -t shelly-nordpool .

echo "Running tests..."

# Run tests in Docker
docker run --rm \
  -v "$(pwd)/tests:/app/tests" \
  -v "$(pwd)/src:/app/src" \
  -v "$(pwd)/output:/app/output" \
  shelly-nordpool python -m pytest tests/ -v

echo "✅ Tests completed" 