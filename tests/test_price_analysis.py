#!/usr/bin/env python3
"""
Unit tests for price analysis module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.price_analysis import PriceAnalyzer


class TestPriceAnalyzerInit(unittest.TestCase):
    """Test PriceAnalyzer initialization"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 5
            }
        }

    def test_init_stores_config(self):
        """Test analyzer stores configuration"""
        analyzer = PriceAnalyzer(self.config)
        
        self.assertEqual(analyzer.token, 'test-token')
        self.assertEqual(analyzer.home_id, 'home-123')
        self.assertEqual(analyzer.num_cheapest_hours, 5)
        self.assertFalse(analyzer.debug)


class TestParseTibberResponse(unittest.TestCase):
    """Test Tibber API response parsing"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 5
            }
        }
        self.analyzer = PriceAnalyzer(self.config)

    def test_parse_valid_response(self):
        """Test parsing valid API response"""
        response = {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "id": "home-123",
                            "address": {
                                "address1": "Test Street 1",
                                "postalCode": "12345",
                                "city": "Test City"
                            },
                            "currentSubscription": {
                                "priceInfo": {
                                    "tomorrow": [
                                        {"startsAt": "2024-01-15T00:00:00Z", "total": 0.5, "energy": 0.3},
                                        {"startsAt": "2024-01-15T01:00:00Z", "total": 0.4, "energy": 0.2},
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        prices = self.analyzer.parse_tibber_response(response)
        
        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0]["total"], 0.5)
        self.assertEqual(prices[1]["total"], 0.4)

    def test_parse_no_homes(self):
        """Test error when no homes in response"""
        response = {
            "data": {
                "viewer": {
                    "homes": []
                }
            }
        }
        
        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(response)
        
        self.assertIn("No homes found", str(context.exception))

    def test_parse_wrong_home_id(self):
        """Test error when home ID doesn't match"""
        response = {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "id": "different-home",
                            "address": {"address1": "Test", "postalCode": "123", "city": "City"},
                            "currentSubscription": {"priceInfo": {"tomorrow": []}}
                        }
                    ]
                }
            }
        }
        
        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(response)
        
        self.assertIn("Could not find home", str(context.exception))

    def test_parse_no_tomorrow_prices(self):
        """Test error when tomorrow's prices not available"""
        response = {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "id": "home-123",
                            "address": {"address1": "Test", "postalCode": "123", "city": "City"},
                            "currentSubscription": {
                                "priceInfo": {
                                    "tomorrow": None
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(response)
        
        self.assertIn("tomorrow", str(context.exception).lower())

    def test_parse_empty_tomorrow_prices(self):
        """Test error when tomorrow's prices list is empty"""
        response = {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "id": "home-123",
                            "address": {"address1": "Test", "postalCode": "123", "city": "City"},
                            "currentSubscription": {
                                "priceInfo": {
                                    "tomorrow": []
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(response)
        
        self.assertIn("tomorrow", str(context.exception).lower())


class TestGetCheapestHours(unittest.TestCase):
    """Test cheapest hours selection"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 3
            }
        }
        self.analyzer = PriceAnalyzer(self.config)

    def test_selects_cheapest_hours(self):
        """Test that cheapest hours are selected correctly"""
        prices = [
            {"startsAt": "2024-01-15T00:00:00Z", "total": 0.5, "energy": 0.3},
            {"startsAt": "2024-01-15T01:00:00Z", "total": 0.2, "energy": 0.1},  # Cheapest
            {"startsAt": "2024-01-15T02:00:00Z", "total": 0.8, "energy": 0.6},
            {"startsAt": "2024-01-15T03:00:00Z", "total": 0.3, "energy": 0.15},  # 2nd cheapest
            {"startsAt": "2024-01-15T04:00:00Z", "total": 0.4, "energy": 0.2},  # 3rd cheapest
        ]
        
        with patch.object(self.analyzer, 'fetch_tibber_data') as mock_fetch:
            with patch.object(self.analyzer, 'parse_tibber_response', return_value=prices):
                mock_fetch.return_value = {}
                
                cheapest = self.analyzer.get_cheapest_hours()
        
        self.assertEqual(len(cheapest), 3)
        # Should be sorted by price (cheapest first in selection)
        totals = [h["total"] for h in cheapest]
        self.assertEqual(sorted(totals), totals)
        self.assertIn(0.2, totals)
        self.assertIn(0.3, totals)
        self.assertIn(0.4, totals)


class TestPriceThreshold(unittest.TestCase):
    """Test price threshold functionality"""

    def test_threshold_adds_additional_hours(self):
        """Test that hours below threshold are added"""
        config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 2,
                'price_threshold': {
                    'enabled': True,
                    'monthly_thresholds': {
                        '1': 0.35  # January threshold
                    }
                }
            }
        }
        analyzer = PriceAnalyzer(config)
        
        prices = [
            {"startsAt": "2024-01-15T00:00:00Z", "total": 0.5, "energy": 0.3},  # Below threshold (0.3 < 0.35)
            {"startsAt": "2024-01-15T01:00:00Z", "total": 0.2, "energy": 0.1},  # Cheapest
            {"startsAt": "2024-01-15T02:00:00Z", "total": 0.8, "energy": 0.6},  # Above threshold
            {"startsAt": "2024-01-15T03:00:00Z", "total": 0.25, "energy": 0.12},  # 2nd cheapest
            {"startsAt": "2024-01-15T04:00:00Z", "total": 0.6, "energy": 0.32},  # Below threshold (0.32 < 0.35)
        ]
        
        with patch.object(analyzer, 'fetch_tibber_data') as mock_fetch:
            with patch.object(analyzer, 'parse_tibber_response', return_value=prices):
                with patch('src.price_analysis.datetime') as mock_datetime:
                    mock_datetime.now.return_value.month = 1  # January
                    mock_datetime.fromisoformat = datetime.fromisoformat
                    mock_fetch.return_value = {}
                    
                    cheapest = analyzer.get_cheapest_hours()
        
        # Should have 2 cheapest + additional hours below threshold
        # 0.1, 0.12 are cheapest 2
        # 0.3 and 0.32 are below threshold 0.35
        self.assertGreaterEqual(len(cheapest), 2)


class TestFetchTibberData(unittest.TestCase):
    """Test Tibber data fetching"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 5
            }
        }

    @patch('src.price_analysis.requests.post')
    def test_fetch_successful(self, mock_post):
        """Test successful API fetch"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"viewer": {"homes": []}}}
        mock_post.return_value = mock_response

        analyzer = PriceAnalyzer(self.config)
        result = analyzer._fetch_tibber_data_internal()

        self.assertIsNotNone(result)
        mock_post.assert_called_once()

    @patch('src.price_analysis.requests.post')
    def test_fetch_http_error(self, mock_post):
        """Test HTTP error raises HTTPRequestError"""
        from src.exceptions import HTTPRequestError

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        analyzer = PriceAnalyzer(self.config)

        with self.assertRaises(HTTPRequestError):
            analyzer._fetch_tibber_data_internal()

    @patch('src.price_analysis.requests.post')
    def test_fetch_connection_error(self, mock_post):
        """Test connection error raises HTTPRequestError"""
        from src.exceptions import HTTPRequestError
        import requests

        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        analyzer = PriceAnalyzer(self.config)

        with self.assertRaises(HTTPRequestError):
            analyzer._fetch_tibber_data_internal()

    @patch('src.price_analysis.requests.post')
    def test_fetch_timeout_error(self, mock_post):
        """Test timeout raises HTTPRequestError"""
        from src.exceptions import HTTPRequestError
        import requests

        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        analyzer = PriceAnalyzer(self.config)

        with self.assertRaises(HTTPRequestError):
            analyzer._fetch_tibber_data_internal()

    @patch('src.price_analysis.requests.post')
    def test_fetch_json_decode_error(self, mock_post):
        """Test invalid JSON raises JSONParseError"""
        from src.exceptions import JSONParseError
        import json

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_post.return_value = mock_response

        analyzer = PriceAnalyzer(self.config)

        with self.assertRaises(JSONParseError):
            analyzer._fetch_tibber_data_internal()


class TestGetCheapestHoursWithThreshold(unittest.TestCase):
    """Test cheapest hours with price threshold"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 2,
                'price_threshold': {
                    'enabled': True,
                    'monthly_thresholds': {
                        '1': 0.35
                    }
                }
            }
        }

    @patch('src.price_analysis.datetime')
    def test_threshold_disabled(self, mock_datetime):
        """Test behavior when threshold is disabled"""
        mock_datetime.now.return_value.month = 1
        mock_datetime.fromisoformat = datetime.fromisoformat

        config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 2,
                'price_threshold': {
                    'enabled': False
                }
            }
        }

        prices = [
            {"startsAt": "2024-01-15T00:00:00Z", "total": 0.5, "energy": 0.3},
            {"startsAt": "2024-01-15T01:00:00Z", "total": 0.2, "energy": 0.1},
            {"startsAt": "2024-01-15T02:00:00Z", "total": 0.3, "energy": 0.15},
        ]

        analyzer = PriceAnalyzer(config)

        with patch.object(analyzer, 'fetch_tibber_data') as mock_fetch:
            with patch.object(analyzer, 'parse_tibber_response', return_value=prices):
                mock_fetch.return_value = {}

                cheapest = analyzer.get_cheapest_hours()

        # Should only return the top 2, no threshold additions
        self.assertEqual(len(cheapest), 2)


class TestGetCheapestHoursErrors(unittest.TestCase):
    """Test error handling in get_cheapest_hours"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'scheduling': {
                'num_cheapest_hours': 5
            }
        }

    def test_no_prices_raises_exception(self):
        """Test that empty prices raises exception"""
        analyzer = PriceAnalyzer(self.config)

        with patch.object(analyzer, 'fetch_tibber_data') as mock_fetch:
            with patch.object(analyzer, 'parse_tibber_response', return_value=[]):
                mock_fetch.return_value = {}

                with self.assertRaises(Exception):
                    analyzer.get_cheapest_hours()

    def test_api_error_propagates(self):
        """Test that API errors propagate correctly"""
        from src.exceptions import TibberAPIError

        analyzer = PriceAnalyzer(self.config)

        with patch.object(analyzer, 'fetch_tibber_data', side_effect=TibberAPIError("API error")):
            with self.assertRaises(TibberAPIError):
                analyzer.get_cheapest_hours()


if __name__ == '__main__':
    unittest.main()
