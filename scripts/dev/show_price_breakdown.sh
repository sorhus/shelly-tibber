#!/bin/bash

# Show detailed price breakdown from Tibber API

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_DIR"

docker build -f Dockerfile.python -t shelly-tibber . > /dev/null 2>&1

docker run --rm \
  -v "$PROJECT_DIR/config.json:/app/config.json:ro" \
  shelly-tibber \
  python -c "
import json
import sys
sys.path.insert(0, '/app/src')

from config import get_config
import requests

config = get_config()

# Fetch with more detailed price info
request_data = {
    'query': '''
    {
      viewer {
        home(id: \"''' + config['tibber']['home_id'] + '''\") {
          currentSubscription {
            priceInfo {
              tomorrow {
                total
                energy
                tax
                startsAt
              }
            }
          }
        }
      }
    }
    '''
}

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {config[\"tibber\"][\"token\"]}'
}

response = requests.post('https://api.tibber.com/v1-beta/gql', headers=headers, json=request_data, timeout=30)
data = response.json()

prices = data['data']['viewer']['home']['currentSubscription']['priceInfo']['tomorrow']

if prices:
    print('📊 Tomorrow\\'s Electricity Prices (first 5 hours):')
    print('='*80)
    for i, price in enumerate(prices[:5]):
        print(f'\\n{price[\"startsAt\"]}')
        print(f'  Total:  {price[\"total\"]:.4f} SEK/kWh  (spot + energy tax)')
        if 'energy' in price:
            print(f'  Energy: {price[\"energy\"]:.4f} SEK/kWh  (spot price)')
        if 'tax' in price:
            print(f'  Tax:    {price[\"tax\"]:.4f} SEK/kWh  (energy tax)')
        remainder = price[\"total\"] - price.get(\"energy\", 0) - price.get(\"tax\", 0)
        print(f'  ➡️  Remainder (should be ~0): {remainder:.4f} SEK/kWh')
    print('\\n' + '='*80)
    print('✅ The \"total\" field = spot price + energy tax')
    print('❌ NOT included: Grid fees, VAT (25%), Tibber monthly fee')
    print('💡 Your actual cost per kWh is higher than \"total\"')
else:
    print('❌ No price data available for tomorrow yet')
"

