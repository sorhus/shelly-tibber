#!/bin/bash

# Test script to see raw Tibber API response
# Run this to debug what the API is returning

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
from price_analysis import PriceAnalyzer

config = get_config()
analyzer = PriceAnalyzer(config)

print('Fetching data from Tibber API...')
response = analyzer.fetch_tibber_data()

print('\n' + '='*80)
print('RAW API RESPONSE:')
print('='*80)
print(json.dumps(response, indent=2))

try:
    homes = response['data']['viewer']['homes']
    for home in homes:
        if home['id'] == config['tibber']['home_id']:
            print('\n' + '='*80)
            print('PRICE INFO FOR YOUR HOME:')
            print('='*80)
            price_info = home['currentSubscription']['priceInfo']
            print(json.dumps(price_info, indent=2))
            
            print('\n' + '='*80)
            print('TOMORROW PRICES:')
            print('='*80)
            tomorrow = price_info.get('tomorrow')
            if tomorrow is None:
                print('❌ tomorrow = None (not available yet)')
            elif isinstance(tomorrow, list):
                if len(tomorrow) == 0:
                    print('❌ tomorrow = [] (empty list)')
                else:
                    print(f'✅ tomorrow has {len(tomorrow)} price points')
                    print('First price point:', json.dumps(tomorrow[0], indent=2))
            else:
                print(f'⚠️  tomorrow is {type(tomorrow)}: {tomorrow}')
            break
except Exception as e:
    print(f'\n❌ Error: {e}')
"

