#!/bin/bash

# Energy Analysis Script
# Analyzes energy usage during scheduled hours for the last 7 days

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "⚡ Energy Analysis - Last 7 Days"
echo "================================="
echo ""
echo "This script analyzes energy usage during scheduled hours by comparing"
echo "output data with Tibber consumption data for the last 7 days."
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Check if Python script exists
if [ ! -f "src/energy_analysis.py" ]; then
    echo "❌ Error: energy_analysis.py not found in src/"
    exit 1
fi

# Build the Docker image if it doesn't exist
echo "🐳 Building Docker image..."
docker build -f "$(pwd)/Dockerfile.python" -t shelly-tibber . > /dev/null 2>&1

# Run the energy analysis in Docker
echo "🚀 Starting energy analysis in Docker container..."
echo ""

docker run --rm \
  -v "$(pwd)/config.json:/app/config.json:ro" \
  -v "$(pwd)/output:/app/output" \
  -v "$(pwd)/logs:/app/logs" \
  shelly-tibber python3 src/energy_analysis.py

echo ""
echo "✅ Energy analysis completed!"
echo ""
echo "📝 Results:"
echo "   - Check the output directory for detailed analysis files"
echo "   - Look for energy_analysis_*.json files in output/YYYY-MM-DD/"
echo ""
echo "🔗 Useful commands:"
echo "   - View latest analysis: ls -la output/\$(date +%Y-%m-%d)/energy_analysis_*.json"
echo "   - Check logs: tail -f logs/cron.log" 