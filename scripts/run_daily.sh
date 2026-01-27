#!/bin/bash

# Daily electricity price scheduling script
# Run this from crontab to schedule Shelly switch for cheapest hours

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
BUILD_EXIT_CODE=${PIPESTATUS[0]}
if [ $BUILD_EXIT_CODE -ne 0 ]; then
    log "ERROR: Docker build failed with exit code $BUILD_EXIT_CODE"
    exit 1
fi

# Resolve mDNS hostname on host before Docker runs
# Docker containers can't use the host's avahi/mDNS resolver, so we resolve
# .local hostnames here and pass the IP via environment variable
SHELLY_HOST_ENV=""
SHELLY_HOST=$(grep -o '"host"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | head -1 | sed 's/.*"host"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
if [[ "$SHELLY_HOST" == *.local ]]; then
    RESOLVED_IP=$(getent hosts "$SHELLY_HOST" 2>/dev/null | awk '{print $1}')
    if [ -n "$RESOLVED_IP" ]; then
        log "Resolved mDNS: $SHELLY_HOST -> $RESOLVED_IP"
        SHELLY_HOST_ENV="-e SHELLY_HOST=$RESOLVED_IP"
    else
        log "WARNING: Could not resolve mDNS hostname $SHELLY_HOST"
    fi
fi

# Run the Docker container
log "Running the scheduler..."
docker run --rm \
    -e FORCE_RUN="$FORCE_RUN" \
    $SHELLY_HOST_ENV \
    -v "$PROJECT_DIR/output:/app/output" \
    -v "$PROJECT_DIR/config.json:/app/config.json:ro" \
    shelly-tibber \
    2>&1 | tee -a "$LOG_FILE"

# Check exit status - use PIPESTATUS to get docker's exit code, not tee's
EXIT_CODE=${PIPESTATUS[0]}
if [ $EXIT_CODE -eq 0 ]; then
    log "Daily scheduling completed successfully"
else
    log "ERROR: Daily scheduling failed with exit code $EXIT_CODE"
    exit 1
fi 