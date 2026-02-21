#!/usr/bin/env python3
"""
Script to get available homes from Tibber API
"""

import sys

from src.config import get_config
from src.http_client import TibberClient

def get_homes(token):
    """Get available homes from Tibber API"""
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

    client = TibberClient(token=token)
    return client.query(query)

def main():
    """Main entry point"""
    print("🏠 Fetching available homes from Tibber...")
    
    try:
        # Load config
        config = get_config(require_home_id=False)
        token = config['tibber']['token']
        
        # Get homes
        data = get_homes(token)
        homes = data['viewer']['homes']
        
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