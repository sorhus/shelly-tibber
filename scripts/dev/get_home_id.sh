#!/bin/bash

# Script to run get_home_id.py in Docker
# Usage: ./scripts/get_home_id.sh

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG_FILE="$PROJECT_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: Config file not found at $CONFIG_FILE"
  exit 1
fi

# Build Docker image if not present
if ! docker image inspect shelly-tibber >/dev/null 2>&1; then
  echo "🔨 Building Docker image..."
  docker build -f "$PROJECT_DIR/Dockerfile.python" -t shelly-tibber "$PROJECT_DIR"
fi

echo "🏠 Running get_home_id.py in Docker..."
docker run --rm \
  -v "$CONFIG_FILE:/app/config.json:ro" \
  shelly-tibber python3 src/get_home_id.py 