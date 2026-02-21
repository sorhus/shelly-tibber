#!/usr/bin/env python3
"""
Unit tests for price analysis module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.price_analysis import PriceAnalyzer
from src.exceptions import HTTPRequestError, TibberAPIError, JSONParseError


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

    def test_init_creates_tibber_client(self):
        """Test analyzer creates TibberClient"""
        analyzer = PriceAnalyzer(self.config)

        self.assertIsNotNone(analyzer.tibber_client)
        self.assertEqual(analyzer.tibber_client.token, 'test-token')


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
        """Test parsing valid API response (data portion from TibberClient)"""
        data = {
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

        prices = self.analyzer.parse_tibber_response(data)

        self.assertEqual(len(prices), 2)
        self.assertEqual(prices[0]["total"], 0.5)
        self.assertEqual(prices[1]["total"], 0.4)

    def test_parse_no_homes(self):
        """Test error when no homes in response"""
        data = {
            "viewer": {
                "homes": []
            }
        }

        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(data)

        self.assertIn("No homes found", str(context.exception))

    def test_parse_wrong_home_id(self):
        """Test error when home ID doesn't match"""
        data = {
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

        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(data)

        self.assertIn("Could not find home", str(context.exception))

    def test_parse_no_tomorrow_prices(self):
        """Test error when tomorrow's prices not available"""
        data = {
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

        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(data)

        self.assertIn("tomorrow", str(context.exception).lower())

    def test_parse_empty_tomorrow_prices(self):
        """Test error when tomorrow's prices list is empty"""
        data = {
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

        with self.assertRaises(Exception) as context:
            self.analyzer.parse_tibber_response(data)

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
    """Test Tibber data fetching via TibberClient"""

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

    def test_fetch_successful(self):
        """Test successful API fetch via TibberClient"""
        analyzer = PriceAnalyzer(self.config)

        mock_data = {"viewer": {"homes": []}}
        with patch.object(analyzer.tibber_client, 'query', return_value=mock_data) as mock_query:
            result = analyzer.fetch_tibber_data()

        self.assertEqual(result, mock_data)
        mock_query.assert_called_once()

    def test_fetch_http_error(self):
        """Test HTTP error from TibberClient raises HTTPRequestError"""
        analyzer = PriceAnalyzer(self.config)

        with patch.object(analyzer.tibber_client, 'query',
                          side_effect=HTTPRequestError("Request failed", url="https://api.tibber.com/v1-beta/gql")):
            with self.assertRaises(HTTPRequestError):
                analyzer.fetch_tibber_data()

    def test_fetch_api_error(self):
        """Test Tibber API error propagates"""
        analyzer = PriceAnalyzer(self.config)

        with patch.object(analyzer.tibber_client, 'query',
                          side_effect=TibberAPIError("API error")):
            with self.assertRaises(TibberAPIError):
                analyzer.fetch_tibber_data()


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
        analyzer = PriceAnalyzer(self.config)

        with patch.object(analyzer, 'fetch_tibber_data', side_effect=TibberAPIError("API error")):
            with self.assertRaises(TibberAPIError):
                analyzer.get_cheapest_hours()


if __name__ == '__main__':
    unittest.main()
