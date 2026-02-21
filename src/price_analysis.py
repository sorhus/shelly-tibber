#!/usr/bin/env python3
"""
Price Analysis Module
Fetches electricity prices from Tibber API and finds the cheapest hours
"""

import json
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

from src.exceptions import (
    TibberAPIError,
    TibberDataNotAvailableError,
    TibberHomeNotFoundError,
    HTTPRequestError,
    JSONParseError,
)
from src.http_client import TibberClient
from src.retry import RetryConfig

logger = logging.getLogger(__name__)

class PriceAnalyzer:
    """Analyzes electricity prices from Tibber API"""
    
    def __init__(self, config: Dict[str, Any], retry_config: RetryConfig = None):
        self.config = config
        self.token = config['tibber']['token']
        self.home_id = config['tibber']['home_id']
        self.num_cheapest_hours = config['scheduling']['num_cheapest_hours']
        self.debug = config['tibber']['debug']
        self.retry_config = retry_config or RetryConfig()

        # Create TibberClient for API calls
        self.tibber_client = TibberClient(
            token=self.token,
            timeout=30,
            retry_config=self.retry_config,
            debug=self.debug
        )
        
    def fetch_tibber_data(self) -> Dict[str, Any]:
        """Fetch price data from Tibber API using TibberClient"""
        logger.debug("Starting price fetch...")

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

        # TibberClient.query() returns the 'data' portion directly
        # and handles retry, error handling, and auth internally
        data = self.tibber_client.query(query)

        logger.debug("Received response from API")

        # Log a sample of the response for debugging
        try:
            logger.debug(f"API Response sample: {json.dumps(data, indent=2)[:1000]}...")
        except Exception:
            pass

        return data
            
    def parse_tibber_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Tibber API response data and extract prices.

        Args:
            data: The 'data' portion of the Tibber GraphQL response
                  (as returned by TibberClient.query())
        """
        logger.debug("Parsing API response...")

        try:
            homes = data["viewer"]["homes"]
            
            if not homes:
                raise TibberAPIError(
                    "No homes found in Tibber account",
                    details={"response": data}
                )
                
            # Find the home with the expected ID
            expected_home = None
            for home in homes:
                if home["id"] == self.home_id:
                    expected_home = home
                    break
                    
            if not expected_home:
                available_homes = [{"id": home["id"], "address": home["address"]} for home in homes]
                raise TibberHomeNotFoundError(
                    f"Could not find home with ID: {self.home_id}",
                    details={"requested_home_id": self.home_id, "available_homes": available_homes}
                )
                
            logger.debug(f"Found correct home: {expected_home['address']['address1']}, {expected_home['address']['city']}")
            
            # Get tomorrow's prices
            price_info = expected_home["currentSubscription"]["priceInfo"]
            logger.debug(f"Price info keys: {list(price_info.keys())}")
            
            prices = price_info.get("tomorrow")
            logger.debug(f"Tomorrow prices type: {type(prices)}, value: {prices}")
            
            if prices is None:
                logger.debug("Tomorrow prices is None - not available yet")
                raise TibberDataNotAvailableError(
                    "Tomorrow's price data not available yet",
                    details={"hint": "Tibber typically publishes tomorrow's prices around 13:00 CET"}
                )
            
            if not isinstance(prices, list):
                logger.debug(f"Tomorrow prices is not a list: {type(prices)}")
                raise TibberAPIError(
                    f"Unexpected price data format: expected list, got {type(prices).__name__}",
                    details={"actual_type": type(prices).__name__}
                )
            
            if len(prices) == 0:
                logger.debug("Tomorrow prices is empty list")
                raise TibberDataNotAvailableError(
                    "Tomorrow's price data is empty",
                    details={"hint": "Tibber returned an empty price list"}
                )
                
            logger.debug(f"Found {len(prices)} price points")
            return prices
            
        except KeyError as e:
            raise TibberAPIError(
                f"Unexpected Tibber API response structure: missing key {str(e)}",
                details={"missing_key": str(e)}
            )
            
    def get_cheapest_hours(self) -> List[Dict[str, Any]]:
        """Get the cheapest hours for tomorrow, considering price thresholds if enabled"""
        logger.info("Fetching electricity prices from Tibber...")
        
        try:
            # Fetch data from Tibber
            response = self.fetch_tibber_data()
            
            # Parse response
            prices = self.parse_tibber_response(response)
            
            if not prices:
                raise TibberDataNotAvailableError("No price data available")
            
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
            
        except (TibberAPIError, TibberDataNotAvailableError, TibberHomeNotFoundError,
                HTTPRequestError, JSONParseError):
            # Re-raise our custom exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Failed to get cheapest hours: {str(e)}")
            raise TibberAPIError(
                f"Unexpected error fetching prices: {str(e)}",
                details={"original_error": str(e)}
            ) 