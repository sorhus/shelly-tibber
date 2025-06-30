#!/usr/bin/env python3
"""
Price Analysis Module
Fetches electricity prices from Tibber API and finds the cheapest hours
"""

import os
import json
import requests
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class PriceAnalyzer:
    """Analyzes electricity prices from Tibber API"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.token = config['tibber']['token']
        self.home_id = config['tibber']['home_id']
        self.num_cheapest_hours = config['analysis']['num_cheapest_hours']
        self.debug = config['tibber']['debug']
        
    def debug_log(self, message: str):
        """Debug logging function"""
        if self.debug:
            logger.debug(f"[DEBUG] {message}")
            
    def fetch_tibber_data(self) -> Dict[str, Any]:
        """Fetch data from Tibber API"""
        self.debug_log("Starting price fetch...")
        
        request_data = {
            "query": """
            {
              viewer {
                homes {
                  id
                  address {
                    address1
                    postalCode
                    city
                  }
                  currentSubscription {
                    priceInfo {
                      tomorrow {
                        total
                        startsAt
                      }
                    }
                  }
                }
              }
            }
            """
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        try:
            response = requests.post(
                "https://api.tibber.com/v1-beta/gql",
                headers=headers,
                json=request_data,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"API request failed with code: {response.status_code}")
                
            self.debug_log("Received response from API")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"HTTP request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API response: {str(e)}")
            
    def parse_tibber_response(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Tibber API response and extract prices"""
        self.debug_log("Parsing API response...")
        
        try:
            homes = response["data"]["viewer"]["homes"]
            
            if not homes:
                raise Exception("No homes found in API response")
                
            # Find the home with the expected ID
            expected_home = None
            for home in homes:
                if home["id"] == self.home_id:
                    expected_home = home
                    break
                    
            if not expected_home:
                available_homes = [{"id": home["id"], "address": home["address"]} for home in homes]
                error_message = (
                    f"Could not find home with ID: {self.home_id}\n"
                    f"Available homes: {json.dumps(available_homes, indent=2)}"
                )
                raise Exception(error_message)
                
            self.debug_log(f"Found correct home: {expected_home['address']['address1']}, {expected_home['address']['city']}")
            
            # Get tomorrow's prices
            prices = expected_home["currentSubscription"]["priceInfo"]["tomorrow"]
            if not prices:
                self.debug_log("No price data available for tomorrow")
                raise Exception("No price data available for tomorrow")
                
            self.debug_log(f"Found {len(prices)} price points")
            return prices
            
        except KeyError as e:
            raise Exception(f"Failed to parse response: Missing key {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to parse response: {str(e)}")
            
    def get_cheapest_hours(self) -> List[Dict[str, Any]]:
        """Get the cheapest hours for tomorrow, excluding the last hour of the day"""
        logger.info("Fetching electricity prices from Tibber...")
        
        try:
            # Fetch data from Tibber
            response = self.fetch_tibber_data()
            
            # Parse response
            prices = self.parse_tibber_response(response)
            
            # Filter out the last hour of the day (23:00-00:00)
            filtered_prices = []
            for price in prices:
                dt = datetime.fromisoformat(price["startsAt"].replace('Z', '+00:00'))
                if dt.hour != 23:  # Exclude 23:00 (last hour of the day)
                    filtered_prices.append(price)
                else:
                    logger.info(f"Excluding last hour of day: {dt.strftime('%H:%M')} - {price['total']:.3f} SEK/kWh")
            
            if not filtered_prices:
                raise Exception("No price data available after excluding last hour of day")
            
            logger.info(f"After filtering: {len(filtered_prices)} hours available (excluded last hour of day)")
            
            # Sort by price and take the cheapest hours
            sorted_prices = sorted(filtered_prices, key=lambda x: x["total"])
            cheapest_hours = sorted_prices[:self.num_cheapest_hours]
            
            logger.info(f"Found {len(cheapest_hours)} cheapest hours (excluding last hour of day)")
            
            # Log the cheapest hours
            for i, price in enumerate(cheapest_hours, 1):
                dt = datetime.fromisoformat(price["startsAt"].replace('Z', '+00:00'))
                logger.info(f"  {i}. {dt.strftime('%H:%M')} - {price['total']:.3f} SEK/kWh")
            
            return cheapest_hours
            
        except Exception as e:
            logger.error(f"Failed to get cheapest hours: {str(e)}")
            raise 