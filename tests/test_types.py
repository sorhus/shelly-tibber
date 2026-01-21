#!/usr/bin/env python3
"""
Unit tests for type definitions
"""

import unittest
import sys
import os
from datetime import datetime, timezone

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import (
    TibberConfig,
    ShellyConfig,
    AnalysisConfig,
    PriceThresholdConfig,
    SchedulingConfig,
    AppConfig,
    PricePoint,
    Address,
    TibberHome,
    ShellyScheduleCall,
    ShellySchedule,
    ScheduleBlock,
    HourlyEnergyUsage,
    DailyEnergySummary,
)


class TestConfigTypes(unittest.TestCase):
    """Test configuration dataclasses"""

    def test_tibber_config_defaults(self):
        """Test TibberConfig with default values"""
        config = TibberConfig(token="test-token", home_id="home-123")
        self.assertEqual(config.token, "test-token")
        self.assertEqual(config.home_id, "home-123")
        self.assertFalse(config.debug)

    def test_shelly_config_defaults(self):
        """Test ShellyConfig with default values"""
        config = ShellyConfig(host="192.168.1.100")
        self.assertEqual(config.host, "192.168.1.100")
        self.assertEqual(config.timeout, 10)
        self.assertEqual(config.username, "")
        self.assertEqual(config.password, "")

    def test_app_config_from_dict(self):
        """Test creating AppConfig from dictionary"""
        data = {
            "tibber": {
                "token": "my-token",
                "home_id": "my-home",
                "debug": True
            },
            "shelly": {
                "host": "192.168.1.50",
                "timeout": 15
            },
            "analysis": {
                "num_cheapest_hours": 8
            },
            "scheduling": {
                "clear_old_schedules": True,
                "price_threshold": {
                    "enabled": True,
                    "monthly_thresholds": {"1": 0.5, "2": 0.6}
                }
            }
        }
        
        config = AppConfig.from_dict(data)
        
        self.assertEqual(config.tibber.token, "my-token")
        self.assertEqual(config.tibber.home_id, "my-home")
        self.assertTrue(config.tibber.debug)
        self.assertEqual(config.shelly.host, "192.168.1.50")
        self.assertEqual(config.shelly.timeout, 15)
        self.assertEqual(config.analysis.num_cheapest_hours, 8)
        self.assertTrue(config.scheduling.clear_old_schedules)
        self.assertTrue(config.scheduling.price_threshold.enabled)
        self.assertEqual(config.scheduling.price_threshold.monthly_thresholds["1"], 0.5)

    def test_app_config_to_dict(self):
        """Test converting AppConfig to dictionary"""
        config = AppConfig(
            tibber=TibberConfig(token="tok", home_id="home", debug=True),
            shelly=ShellyConfig(host="192.168.1.1", timeout=20),
            analysis=AnalysisConfig(num_cheapest_hours=5),
            scheduling=SchedulingConfig(
                clear_old_schedules=True,
                price_threshold=PriceThresholdConfig(enabled=True, monthly_thresholds={"1": 0.3})
            )
        )
        
        data = config.to_dict()
        
        self.assertEqual(data["tibber"]["token"], "tok")
        self.assertEqual(data["shelly"]["timeout"], 20)
        self.assertEqual(data["analysis"]["num_cheapest_hours"], 5)
        self.assertTrue(data["scheduling"]["price_threshold"]["enabled"])

    def test_app_config_from_dict_with_missing_optional(self):
        """Test AppConfig handles missing optional fields"""
        data = {
            "tibber": {"token": "tok", "home_id": "home"},
            "shelly": {"host": "192.168.1.1"},
            "analysis": {"num_cheapest_hours": 10}
        }
        
        config = AppConfig.from_dict(data)
        
        self.assertFalse(config.tibber.debug)
        self.assertFalse(config.scheduling.clear_old_schedules)
        self.assertFalse(config.scheduling.price_threshold.enabled)


class TestPricePoint(unittest.TestCase):
    """Test PricePoint dataclass"""

    def test_from_dict_with_z_suffix(self):
        """Test parsing timestamp with Z suffix"""
        data = {
            "startsAt": "2024-01-15T10:00:00Z",
            "total": 1.23,
            "energy": 0.45
        }
        
        price = PricePoint.from_dict(data)
        
        self.assertEqual(price.starts_at.hour, 10)
        self.assertEqual(price.total, 1.23)
        self.assertEqual(price.energy, 0.45)

    def test_from_dict_with_offset(self):
        """Test parsing timestamp with timezone offset"""
        data = {
            "startsAt": "2024-01-15T10:00:00+01:00",
            "total": 1.23,
            "energy": 0.45
        }
        
        price = PricePoint.from_dict(data)
        
        self.assertEqual(price.starts_at.hour, 10)

    def test_from_dict_energy_fallback(self):
        """Test energy falls back to total if not present"""
        data = {
            "startsAt": "2024-01-15T10:00:00Z",
            "total": 1.23
        }
        
        price = PricePoint.from_dict(data)
        
        self.assertEqual(price.energy, 1.23)

    def test_to_dict(self):
        """Test converting PricePoint to dict"""
        price = PricePoint(
            starts_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            total=1.23,
            energy=0.45
        )
        
        data = price.to_dict()
        
        self.assertIn("2024-01-15", data["startsAt"])
        self.assertEqual(data["total"], 1.23)
        self.assertEqual(data["energy"], 0.45)


class TestShellyTypes(unittest.TestCase):
    """Test Shelly-related dataclasses"""

    def test_schedule_call_from_dict(self):
        """Test ShellyScheduleCall from dict"""
        data = {
            "method": "Switch.Set",
            "params": {"id": 0, "on": True}
        }
        
        call = ShellyScheduleCall.from_dict(data)
        
        self.assertEqual(call.method, "Switch.Set")
        self.assertEqual(call.params["on"], True)

    def test_schedule_from_dict(self):
        """Test ShellySchedule from dict"""
        data = {
            "id": 123,
            "enable": True,
            "timespec": "0 0 10 * * 1",
            "calls": [
                {"method": "Switch.Set", "params": {"id": 0, "on": True}}
            ]
        }
        
        schedule = ShellySchedule.from_dict(data)
        
        self.assertEqual(schedule.id, 123)
        self.assertTrue(schedule.enable)
        self.assertEqual(schedule.timespec, "0 0 10 * * 1")
        self.assertEqual(len(schedule.calls), 1)
        self.assertEqual(schedule.calls[0].method, "Switch.Set")


class TestScheduleBlock(unittest.TestCase):
    """Test ScheduleBlock dataclass"""

    def test_duration_hours(self):
        """Test duration calculation"""
        block = ScheduleBlock(
            start=datetime(2024, 1, 15, 10, 0, 0),
            end=datetime(2024, 1, 15, 13, 0, 0)
        )
        
        self.assertEqual(block.duration_hours, 3.0)

    def test_duration_hours_fractional(self):
        """Test fractional duration"""
        block = ScheduleBlock(
            start=datetime(2024, 1, 15, 10, 0, 0),
            end=datetime(2024, 1, 15, 11, 30, 0)
        )
        
        self.assertEqual(block.duration_hours, 1.5)


class TestDailyEnergySummary(unittest.TestCase):
    """Test DailyEnergySummary dataclass"""

    def test_efficiency_ratio(self):
        """Test efficiency ratio calculation"""
        summary = DailyEnergySummary(
            date="2024-01-15",
            total_consumption=10.0,
            total_cost=15.0,
            scheduled_consumption=7.5,
            scheduled_cost=10.0,
            scheduled_hours=8,
            total_hours=24
        )
        
        self.assertEqual(summary.efficiency_ratio, 0.75)

    def test_efficiency_ratio_zero_consumption(self):
        """Test efficiency ratio with zero consumption"""
        summary = DailyEnergySummary(
            date="2024-01-15",
            total_consumption=0.0,
            total_cost=0.0,
            scheduled_consumption=0.0,
            scheduled_cost=0.0,
            scheduled_hours=0,
            total_hours=24
        )
        
        self.assertEqual(summary.efficiency_ratio, 0.0)


if __name__ == '__main__':
    unittest.main()
