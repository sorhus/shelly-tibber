#!/usr/bin/env python3
"""
Unit tests for energy analysis module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from src.energy_analysis import EnergyAnalyzer, EnergyUsage, DailyEnergySummary
from src.exceptions import TibberAPIError
from src.models import AppConfig, TibberConfig, ShellyConfig, SchedulingConfig


def make_config(token='test-token', home_id='home-123', debug=False):
    return AppConfig(
        tibber=TibberConfig(token=token, home_id=home_id, debug=debug),
        shelly=ShellyConfig(host='192.168.1.100'),
        scheduling=SchedulingConfig()
    )


class TestEnergyAnalyzerInit(unittest.TestCase):
    """Test EnergyAnalyzer initialization"""

    def setUp(self):
        self.config = make_config()

    @patch('src.energy_analysis.TibberClient')
    def test_init_stores_config(self, mock_client):
        """Test analyzer stores configuration"""
        analyzer = EnergyAnalyzer(self.config)

        self.assertEqual(analyzer.home_id, 'home-123')
        self.assertFalse(analyzer.debug)

    @patch('src.energy_analysis.TibberClient')
    def test_init_creates_tibber_client(self, mock_client_cls):
        """Test analyzer creates TibberClient"""
        analyzer = EnergyAnalyzer(self.config)

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args[1]
        self.assertEqual(call_kwargs['token'], 'test-token')


class TestParseConsumptionData(unittest.TestCase):
    """Test consumption data parsing"""

    def setUp(self):
        self.config = make_config()

    @patch('src.energy_analysis.TibberClient')
    def test_parse_valid_response(self, mock_client):
        """Test parsing valid API response"""
        analyzer = EnergyAnalyzer(self.config)

        # Use UTC times to avoid timezone conversion issues
        response = {
            "data": {
                "viewer": {
                    "home": {
                        "consumption": {
                            "nodes": [
                                {
                                    "from": "2024-01-15T00:00:00+00:00",
                                    "to": "2024-01-15T01:00:00+00:00",
                                    "consumption": 1.5,
                                    "cost": 0.75,
                                    "unitPrice": 0.5
                                },
                                {
                                    "from": "2024-01-15T01:00:00+00:00",
                                    "to": "2024-01-15T02:00:00+00:00",
                                    "consumption": 2.0,
                                    "cost": 1.0,
                                    "unitPrice": 0.5
                                }
                            ]
                        }
                    }
                }
            }
        }

        result = analyzer.parse_consumption_data(response, "2024-01-14", "2024-01-16")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].consumption, 1.5)
        self.assertEqual(result[1].consumption, 2.0)

    @patch('src.energy_analysis.TibberClient')
    def test_parse_empty_response(self, mock_client):
        """Test error on empty response"""
        analyzer = EnergyAnalyzer(self.config)

        with self.assertRaises(TibberAPIError):
            analyzer.parse_consumption_data(None, "2024-01-15", "2024-01-15")

    @patch('src.energy_analysis.TibberClient')
    def test_parse_response_with_errors(self, mock_client):
        """Test error on response with GraphQL errors"""
        analyzer = EnergyAnalyzer(self.config)

        response = {
            "errors": [{"message": "Some error"}]
        }

        with self.assertRaises(TibberAPIError):
            analyzer.parse_consumption_data(response, "2024-01-15", "2024-01-15")

    @patch('src.energy_analysis.TibberClient')
    def test_parse_missing_data_field(self, mock_client):
        """Test error on missing data field"""
        analyzer = EnergyAnalyzer(self.config)

        response = {"something": "else"}

        with self.assertRaises(TibberAPIError):
            analyzer.parse_consumption_data(response, "2024-01-15", "2024-01-15")

    @patch('src.energy_analysis.TibberClient')
    def test_parse_missing_viewer(self, mock_client):
        """Test error on missing viewer field"""
        analyzer = EnergyAnalyzer(self.config)

        response = {"data": {}}

        with self.assertRaises(TibberAPIError):
            analyzer.parse_consumption_data(response, "2024-01-15", "2024-01-15")

    @patch('src.energy_analysis.TibberClient')
    def test_parse_empty_nodes(self, mock_client):
        """Test empty nodes returns empty list"""
        analyzer = EnergyAnalyzer(self.config)

        response = {
            "data": {
                "viewer": {
                    "home": {
                        "consumption": {
                            "nodes": []
                        }
                    }
                }
            }
        }

        result = analyzer.parse_consumption_data(response, "2024-01-15", "2024-01-15")
        self.assertEqual(result, [])

    @patch('src.energy_analysis.TibberClient')
    def test_parse_handles_null_values(self, mock_client):
        """Test parsing handles null consumption values"""
        analyzer = EnergyAnalyzer(self.config)

        response = {
            "data": {
                "viewer": {
                    "home": {
                        "consumption": {
                            "nodes": [
                                {
                                    "from": "2024-01-15T00:00:00+00:00",
                                    "to": "2024-01-15T01:00:00+00:00",
                                    "consumption": None,
                                    "cost": None,
                                    "unitPrice": None
                                }
                            ]
                        }
                    }
                }
            }
        }

        result = analyzer.parse_consumption_data(response, "2024-01-14", "2024-01-16")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].consumption, 0)
        self.assertEqual(result[0].cost, 0)
        self.assertEqual(result[0].price, 0)


class TestMarkScheduledHours(unittest.TestCase):
    """Test marking of scheduled hours"""

    def setUp(self):
        self.config = make_config()

    @patch('src.energy_analysis.TibberClient')
    def test_mark_scheduled_hours(self, mock_client):
        """Test marking hours as scheduled"""
        analyzer = EnergyAnalyzer(self.config)

        energy_usage = [
            EnergyUsage(date="2024-01-15", hour=0, consumption=1.0, cost=0.5, price=0.5, was_scheduled=False),
            EnergyUsage(date="2024-01-15", hour=1, consumption=1.0, cost=0.5, price=0.5, was_scheduled=False),
            EnergyUsage(date="2024-01-15", hour=2, consumption=1.0, cost=0.5, price=0.5, was_scheduled=False),
        ]

        output_data = [
            {
                "date": "2024-01-15",
                "consecutive_blocks": [
                    ("2024-01-15T00:00:00+00:00", "2024-01-15T02:00:00+00:00")
                ]
            }
        ]

        result = analyzer.mark_scheduled_hours(energy_usage, output_data)

        self.assertTrue(result[0].was_scheduled)  # Hour 0
        self.assertTrue(result[1].was_scheduled)  # Hour 1
        self.assertFalse(result[2].was_scheduled)  # Hour 2 (end time is exclusive)

    @patch('src.energy_analysis.TibberClient')
    def test_mark_no_scheduled_hours(self, mock_client):
        """Test when no hours are scheduled"""
        analyzer = EnergyAnalyzer(self.config)

        energy_usage = [
            EnergyUsage(date="2024-01-15", hour=0, consumption=1.0, cost=0.5, price=0.5, was_scheduled=False),
        ]

        output_data = []  # No scheduled data

        result = analyzer.mark_scheduled_hours(energy_usage, output_data)

        self.assertFalse(result[0].was_scheduled)


class TestCalculateDailySummaries(unittest.TestCase):
    """Test daily summary calculations"""

    def setUp(self):
        self.config = make_config()

    @patch('src.energy_analysis.TibberClient')
    def test_calculate_daily_summaries(self, mock_client):
        """Test daily summary calculation"""
        analyzer = EnergyAnalyzer(self.config)

        energy_usage = [
            EnergyUsage(date="2024-01-15", hour=0, consumption=1.0, cost=0.5, price=0.5, was_scheduled=True),
            EnergyUsage(date="2024-01-15", hour=1, consumption=2.0, cost=1.0, price=0.5, was_scheduled=True),
            EnergyUsage(date="2024-01-15", hour=2, consumption=3.0, cost=1.5, price=0.5, was_scheduled=False),
        ]

        result = analyzer.calculate_daily_summaries(energy_usage)

        self.assertEqual(len(result), 1)
        summary = result[0]
        self.assertEqual(summary.date, "2024-01-15")
        self.assertEqual(summary.total_consumption, 6.0)
        self.assertEqual(summary.total_cost, 3.0)
        self.assertEqual(summary.scheduled_consumption, 3.0)
        self.assertEqual(summary.scheduled_cost, 1.5)
        self.assertEqual(summary.scheduled_hours, 2)
        self.assertEqual(summary.total_hours, 3)
        self.assertEqual(summary.efficiency_ratio, 0.5)

    @patch('src.energy_analysis.TibberClient')
    def test_calculate_multiple_days(self, mock_client):
        """Test summary calculation for multiple days"""
        analyzer = EnergyAnalyzer(self.config)

        energy_usage = [
            EnergyUsage(date="2024-01-15", hour=0, consumption=1.0, cost=0.5, price=0.5, was_scheduled=True),
            EnergyUsage(date="2024-01-16", hour=0, consumption=2.0, cost=1.0, price=0.5, was_scheduled=False),
        ]

        result = analyzer.calculate_daily_summaries(energy_usage)

        self.assertEqual(len(result), 2)
        # Results are sorted by date descending (newest first)
        self.assertEqual(result[0].date, "2024-01-16")
        self.assertEqual(result[1].date, "2024-01-15")

    @patch('src.energy_analysis.TibberClient')
    def test_zero_consumption(self, mock_client):
        """Test efficiency ratio with zero consumption"""
        analyzer = EnergyAnalyzer(self.config)

        energy_usage = [
            EnergyUsage(date="2024-01-15", hour=0, consumption=0, cost=0, price=0.5, was_scheduled=False),
        ]

        result = analyzer.calculate_daily_summaries(energy_usage)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].efficiency_ratio, 0)


class TestFetchTibberConsumption(unittest.TestCase):
    """Test Tibber consumption fetching"""

    def setUp(self):
        self.config = make_config()

    @patch('src.energy_analysis.TibberClient')
    def test_fetch_calls_tibber_client(self, mock_client_cls):
        """Test that fetch uses TibberClient"""
        mock_client = mock_client_cls.return_value
        mock_client.query.return_value = {
            "viewer": {
                "home": {
                    "consumption": {"nodes": []}
                }
            }
        }

        analyzer = EnergyAnalyzer(self.config)
        result = analyzer.fetch_tibber_consumption("2024-01-15", "2024-01-16")

        mock_client.query.assert_called_once()
        # Check that variables were passed
        call_args = mock_client.query.call_args
        self.assertIn('homeId', call_args[0][1])
        self.assertEqual(call_args[0][1]['homeId'], 'home-123')


if __name__ == '__main__':
    unittest.main()
