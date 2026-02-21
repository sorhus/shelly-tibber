#!/bin/bash

# Reboot Shelly device and verify mDNS comes back

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
CONFIG_FILE="$PROJECT_DIR/config.json"
CACHED_IP_FILE="$PROJECT_DIR/.last_known_shelly_ip"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found at $CONFIG_FILE"
    exit 1
fi

SHELLY_HOST=$(grep -o '"host"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | head -1 | sed 's/.*"host"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

# Determine the IP to use
if [[ "$SHELLY_HOST" != *.local ]]; then
    SHELLY_IP="$SHELLY_HOST"
elif [ -f "$CACHED_IP_FILE" ]; then
    SHELLY_IP=$(cat "$CACHED_IP_FILE")
    echo "Using cached IP: $SHELLY_IP"
else
    SHELLY_IP=$(getent hosts "$SHELLY_HOST" 2>/dev/null | awk '{print $1}')
    if [ -z "$SHELLY_IP" ]; then
        echo "ERROR: Could not resolve $SHELLY_HOST and no cached IP available"
        exit 1
    fi
fi

echo "Rebooting Shelly at $SHELLY_IP..."
RESPONSE=$(curl -s -w "\n%{http_code}" "http://$SHELLY_IP/rpc/Shelly.Reboot" 2>&1)
HTTP_CODE=$(echo "$RESPONSE" | tail -1)

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: Reboot request failed (HTTP $HTTP_CODE)"
    echo "$RESPONSE"
    exit 1
fi

echo "Reboot initiated. Waiting for device to come back..."

# Wait for device to go down
sleep 5

# Wait for device to come back (ping)
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if ping -c 1 -W 1 "$SHELLY_IP" >/dev/null 2>&1; then
        echo "Device is back online after ${ELAPSED}s"
        break
    fi
    ELAPSED=$((ELAPSED + 2))
    sleep 2
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo "ERROR: Device did not come back within ${MAX_WAIT}s"
    exit 1
fi

# Give mDNS a moment to advertise
sleep 5

# Check mDNS resolution
if [[ "$SHELLY_HOST" == *.local ]]; then
    echo "Checking mDNS resolution for $SHELLY_HOST..."
    RESOLVED_IP=$(avahi-resolve -n "$SHELLY_HOST" 2>/dev/null | awk '{print $2}')
    if [ -n "$RESOLVED_IP" ]; then
        echo "mDNS resolved: $SHELLY_HOST -> $RESOLVED_IP"
        echo "$RESOLVED_IP" > "$CACHED_IP_FILE"
        echo "Cached IP updated"
    else
        echo "WARNING: mDNS still not resolving. Device is reachable by IP but not advertising mDNS."
        echo "The cached IP ($SHELLY_IP) will be used as fallback by run_daily.sh."
    fi
fi
