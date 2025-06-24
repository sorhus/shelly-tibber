#!/bin/bash

# Daily electricity price scheduling script
# Run this from crontab to schedule Shelly switch for cheapest hours

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FORCE_RUN="${FORCE_RUN:-false}"

# Log file
LOG_FILE="$PROJECT_DIR/logs/cron.log"
mkdir -p "$(dirname "$LOG_FILE")"

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check if config file exists
CONFIG_FILE="$PROJECT_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    log "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

log "Starting daily electricity price scheduling"
log "FORCE_RUN mode: $FORCE_RUN"

# Build Docker image to ensure latest code
log "Building Docker image to ensure latest code..."
docker build -f Dockerfile.python -t shelly-tibber . 2>&1 | tee -a "$LOG_FILE"

# Run the Docker container
log "Running the scheduler..."
docker run --rm \
    -e FORCE_RUN="$FORCE_RUN" \
    -v "$PROJECT_DIR/output:/app/output" \
    -v "$PROJECT_DIR/config.json:/app/config.json:ro" \
    shelly-tibber \
    2>&1 | tee -a "$LOG_FILE"

# Check exit status
if [ $? -eq 0 ]; then
    log "Daily scheduling completed successfully"
else
    log "ERROR: Daily scheduling failed"
    exit 1
fi 