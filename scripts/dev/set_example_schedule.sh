#!/bin/bash

# Set example schedule on Shelly device using Docker
# This script builds the Docker image and runs the set_example_schedule.py script

set -e

echo "🔧 Setting example schedule on Shelly device..."
echo "Building Docker image to ensure latest code..."

# Build the Docker image
docker build -f Dockerfile.python -t shelly-tibber .

echo "Running the example schedule script..."

# Run the script in Docker
docker run --rm \
  -v "$(pwd)/output:/app/output" \
  -v "$(pwd)/config.json:/app/config.json:ro" \
  shelly-tibber python3 src/set_example_schedule.py

echo "✅ Example schedule script completed" 