#!/usr/bin/env python3
"""
Script to get available homes from Tibber API
"""

import requests
import json
import sys

from src.config import get_config

def get_homes(token):
    """Get available homes from Tibber API"""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    query = """
    {
      viewer {
        homes {
          id
          address {
            address1
            postalCode
            city
          }
        }
      }
    }
    """
    
    try:
        response = requests.post(
            'https://api.tibber.com/v1-beta/gql',
            headers=headers,
            json={'query': query},
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"API request failed with code: {response.status_code}")
            
        return response.json()
        
    except Exception as e:
        raise Exception(f"Failed to fetch homes: {str(e)}")

def main():
    """Main entry point"""
    print("🏠 Fetching available homes from Tibber...")
    
    try:
        # Load config
        config = get_config(require_home_id=False)
        token = config['tibber']['token']
        
        # Get homes
        data = get_homes(token)
        homes = data['data']['viewer']['homes']
        
        print(f"\n✅ Found {len(homes)} home(s):")
        print("=" * 50)
        
        for i, home in enumerate(homes, 1):
            address = home['address']
            print(f"{i}. ID: {home['id']}")
            print(f"   Address: {address['address1']}")
            print(f"   Location: {address['postalCode']} {address['city']}")
            print()
        
        print("📋 Copy the home ID you want to use for your configuration.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 