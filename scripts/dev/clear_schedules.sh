#!/bin/bash

# Clear all schedules from Shelly device using Docker

echo "🗑️  Clearing all schedules from Shelly device..."

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG_FILE="$PROJECT_DIR/config.json"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Create output and logs directories if they don't exist
mkdir -p "$PROJECT_DIR/output" "$PROJECT_DIR/logs"

echo "📋 Using configuration from: $CONFIG_FILE"
echo ""

# Change to project directory
cd "$PROJECT_DIR"

# Build Docker image
echo "🔨 Building Docker image..."
docker build -f Dockerfile.python -t shelly-tibber .

echo "🚀 Running schedule clear script..."
docker run --rm \
  -v "$PROJECT_DIR/output:/app/output" \
  -v "$PROJECT_DIR/config.json:/app/config.json:ro" \
  shelly-tibber python3 src/clear_schedules.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All schedules cleared successfully!"
else
    echo ""
    echo "❌ Failed to clear schedules. Check the error messages above."
    exit 1
fi 