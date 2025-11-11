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
                        energy
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
            json_response = response.json()
            
            # Log a sample of the response for debugging
            if self.debug:
                try:
                    import json as json_module
                    self.debug_log(f"API Response sample: {json_module.dumps(json_response, indent=2)[:1000]}...")
                except:
                    pass
            
            return json_response
            
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
            price_info = expected_home["currentSubscription"]["priceInfo"]
            self.debug_log(f"Price info keys: {list(price_info.keys())}")
            
            prices = price_info.get("tomorrow")
            self.debug_log(f"Tomorrow prices type: {type(prices)}, value: {prices}")
            
            if prices is None:
                self.debug_log("Tomorrow prices is None - not available yet")
                raise Exception("No price data available for tomorrow")
            
            if not isinstance(prices, list):
                self.debug_log(f"Tomorrow prices is not a list: {type(prices)}")
                raise Exception(f"Unexpected price data format: {type(prices)}")
            
            if len(prices) == 0:
                self.debug_log("Tomorrow prices is empty list")
                raise Exception("No price data available for tomorrow")
                
            self.debug_log(f"Found {len(prices)} price points")
            return prices
            
        except KeyError as e:
            raise Exception(f"Failed to parse response: Missing key {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to parse response: {str(e)}")
            
    def get_cheapest_hours(self) -> List[Dict[str, Any]]:
        """Get the cheapest hours for tomorrow, considering price thresholds if enabled"""
        logger.info("Fetching electricity prices from Tibber...")
        
        try:
            # Fetch data from Tibber
            response = self.fetch_tibber_data()
            
            # Parse response
            prices = self.parse_tibber_response(response)
            
            if not prices:
                raise Exception("No price data available")
            
            logger.info(f"Found {len(prices)} hours available")
            
            # Sort by price to get the cheapest hours
            sorted_prices = sorted(prices, key=lambda x: x["total"])
            cheapest_hours = sorted_prices[:self.num_cheapest_hours]
            
            logger.info(f"Selected {len(cheapest_hours)} cheapest hours")
            
            # Check if price threshold is enabled to add additional hours
            threshold_config = self.config.get('scheduling', {}).get('price_threshold', {})
            threshold_enabled = threshold_config.get('enabled', False)
            
            if threshold_enabled:
                # Get the current month (1-12)
                current_month = datetime.now().month
                monthly_thresholds = threshold_config.get('monthly_thresholds', {})
                threshold = monthly_thresholds.get(str(current_month))
                
                if threshold is not None:
                    logger.info(f"Spot price threshold enabled for month {current_month}: {threshold:.3f} SEK/kWh")
                    
                    # Find all hours with spot price below threshold
                    below_threshold = [p for p in prices if p.get("energy", p["total"]) < threshold]
                    
                    # Combine cheapest hours with hours below threshold (remove duplicates)
                    cheapest_set = {p["startsAt"] for p in cheapest_hours}
                    additional_hours = [p for p in below_threshold if p["startsAt"] not in cheapest_set]
                    
                    if additional_hours:
                        logger.info(f"Found {len(additional_hours)} additional hours with spot price below threshold (not in top {self.num_cheapest_hours})")
                        for price in additional_hours:
                            dt = datetime.fromisoformat(price["startsAt"].replace('Z', '+00:00'))
                            spot = price.get("energy", price["total"])
                            logger.info(f"  + {dt.strftime('%H:%M')} - spot: {spot:.3f} SEK/kWh (below {threshold:.3f})")
                        
                        cheapest_hours = cheapest_hours + additional_hours
                        logger.info(f"Total hours to schedule: {len(cheapest_hours)} ({self.num_cheapest_hours} cheapest + {len(additional_hours)} below spot threshold)")
                    else:
                        logger.info(f"No additional hours with spot price below threshold ({threshold:.3f} SEK/kWh)")
                else:
                    logger.warning(f"No threshold configured for month {current_month}")
            
            # Log the cheapest hours
            for i, price in enumerate(cheapest_hours, 1):
                dt = datetime.fromisoformat(price["startsAt"].replace('Z', '+00:00'))
                spot = price.get("energy", price["total"])
                logger.info(f"  {i}. {dt.strftime('%H:%M')} - total: {price['total']:.3f} SEK/kWh (spot: {spot:.3f})")
            
            return cheapest_hours
            
        except Exception as e:
            logger.error(f"Failed to get cheapest hours: {str(e)}")
            raise 