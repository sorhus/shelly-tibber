#!/usr/bin/env python3
"""
Integration tests for the main scheduler orchestrator
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.schedule_cheapest_hours import CheapestHoursScheduler
from src.health_check import StatusManager


class TestCheapestHoursSchedulerInit(unittest.TestCase):
    """Test CheapestHoursScheduler initialization"""

    def setUp(self):
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 5,
                'clear_old_schedules': False
            }
        }

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    def test_init_stores_config(self, mock_price_analyzer, mock_shelly):
        """Test scheduler stores configuration"""
        scheduler = CheapestHoursScheduler(self.config)

        self.assertEqual(scheduler.config, self.config)
        self.assertFalse(scheduler.dry_run)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    def test_init_dry_run_mode(self, mock_price_analyzer, mock_shelly):
        """Test scheduler initializes in dry-run mode"""
        scheduler = CheapestHoursScheduler(self.config, dry_run=True)

        self.assertTrue(scheduler.dry_run)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    def test_init_with_status_manager(self, mock_price_analyzer, mock_shelly):
        """Test scheduler accepts custom status manager"""
        status_manager = Mock(spec=StatusManager)
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)

        self.assertEqual(scheduler.status_manager, status_manager)


class TestSuccessfulScheduling(unittest.TestCase):
    """Test successful scheduling flow"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }
        # Sample price data for tomorrow
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.sample_prices = [
            {"startsAt": (tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.2},
            {"startsAt": (tomorrow.replace(hour=3, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.3},
            {"startsAt": (tomorrow.replace(hour=4, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.4},
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_successful_run_writes_status(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test successful run writes success status"""
        # Setup mocks
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1, 2], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=3))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_file = os.path.join(self.temp_dir, 'status.json')
        status_manager = StatusManager(status_file)

        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        last_run = status_manager.get_last_run()
        self.assertIsNotNone(last_run)
        self.assertEqual(last_run.status, "success")
        self.assertEqual(last_run.schedules_created, 2)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_successful_run_returns_true(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test successful run returns True"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)


class TestAlreadyRunToday(unittest.TestCase):
    """Test behavior when scheduler has already run today"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_skips_if_already_run_today(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test scheduler skips if already run today"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_shelly = mock_shelly_cls.return_value

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = True  # Success file exists
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        scheduler = CheapestHoursScheduler(self.config)
        result = scheduler.run()

        self.assertTrue(result)  # Returns True (success) when skipping
        mock_price_analyzer.get_cheapest_hours.assert_not_called()  # Should not fetch prices


class TestForceRunOverride(unittest.TestCase):
    """Test FORCE_RUN environment variable override"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.sample_prices = [
            {"startsAt": (tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.2},
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        # Clean up environment variable
        if 'FORCE_RUN' in os.environ:
            del os.environ['FORCE_RUN']

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_force_run_overrides_skip(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test FORCE_RUN=true overrides the skip behavior"""
        os.environ['FORCE_RUN'] = 'true'

        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = True  # Success file exists
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        mock_price_analyzer.get_cheapest_hours.assert_called_once()  # Should fetch prices with FORCE_RUN


class TestNoPricesAvailable(unittest.TestCase):
    """Test handling of no prices available"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_no_prices_returns_false(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test scheduler returns False when no prices available"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = []  # No prices

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertFalse(result)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_no_prices_writes_failure_status(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test scheduler writes failure status when no prices"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = []  # No prices

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_file = os.path.join(self.temp_dir, 'status.json')
        status_manager = StatusManager(status_file)
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertFalse(result)
        last_run = status_manager.get_last_run()
        self.assertIsNotNone(last_run)
        self.assertEqual(last_run.status, "failure")
        self.assertIn("No cheapest hours", last_run.error_message)


class TestDryRunMode(unittest.TestCase):
    """Test dry-run mode behavior"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.sample_prices = [
            {"startsAt": (tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.2},
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_dry_run_does_not_write_success_file(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test dry-run mode does not write success file"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, dry_run=True, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        mock_file_manager.write_success_file.assert_not_called()

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_dry_run_writes_status_with_dry_run_flag(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test dry-run mode writes status with dry_run flag"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_file = os.path.join(self.temp_dir, 'status.json')
        status_manager = StatusManager(status_file)
        scheduler = CheapestHoursScheduler(self.config, dry_run=True, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        last_run = status_manager.get_last_run()
        self.assertIsNotNone(last_run)
        self.assertTrue(last_run.dry_run)


class TestMidnightHourHandling(unittest.TestCase):
    """Test handling of midnight hour (00:00) in cheapest hours"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }
        # Create prices that include midnight
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.midnight_prices = [
            {"startsAt": (tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.1},  # Midnight
            {"startsAt": (tomorrow.replace(hour=1, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.2},
            {"startsAt": (tomorrow.replace(hour=23, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.3},
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_midnight_hour_checks_for_conflicts(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test that midnight hour triggers conflict check"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.midnight_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []  # No conflicting schedules
        mock_shelly.create_price_based_schedules.return_value = ([1, 2, 3], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=2))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        # Verify list_schedules was called to check for conflicts
        mock_shelly.list_schedules.assert_called()


class TestClearOldSchedules(unittest.TestCase):
    """Test old schedule cleanup behavior"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': True
            }
        }
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        self.sample_prices = [
            {"startsAt": (tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)).isoformat(), "total": 0.2},
        ]

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_clear_old_schedules_deletes_all_except_today(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test that clear_old_schedules=True deletes all weekdays except today"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])
        mock_shelly.delete_schedules_for_weekdays.return_value = 5

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        # Verify delete_schedules_for_weekdays was called
        mock_shelly.delete_schedules_for_weekdays.assert_called_once()

        # Verify it was called with 6 weekdays (all except today)
        call_args = mock_shelly.delete_schedules_for_weekdays.call_args[0][0]
        self.assertEqual(len(call_args), 6)

        # Verify today's weekday is NOT in the list
        today_cron = (datetime.now().weekday() + 1) % 7
        self.assertNotIn(today_cron, call_args)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_clear_old_schedules_false_does_not_delete(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test that clear_old_schedules=False does not delete any schedules"""
        self.config['scheduling']['clear_old_schedules'] = False

        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)
        # Verify delete_schedules_for_weekdays was NOT called
        mock_shelly.delete_schedules_for_weekdays.assert_not_called()

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_clear_old_schedules_correct_weekdays(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test that correct weekdays are passed for deletion"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.return_value = self.sample_prices

        mock_shelly = mock_shelly_cls.return_value
        mock_shelly.list_schedules.return_value = []
        mock_shelly.create_price_based_schedules.return_value = ([1], [
            (datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(hours=1))
        ])
        mock_shelly.delete_schedules_for_weekdays.return_value = 0

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager._get_daily_dir.return_value = self.temp_dir
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_manager = StatusManager(os.path.join(self.temp_dir, 'status.json'))
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertTrue(result)

        # Get the weekdays that were passed for deletion
        call_args = mock_shelly.delete_schedules_for_weekdays.call_args[0][0]

        # All weekdays should be 0-6
        for weekday in call_args:
            self.assertIn(weekday, range(7))

        # Should contain exactly all weekdays except today
        today_cron = (datetime.now().weekday() + 1) % 7
        expected_weekdays = [w for w in range(7) if w != today_cron]
        self.assertEqual(sorted(call_args), sorted(expected_weekdays))


class TestExceptionHandling(unittest.TestCase):
    """Test exception handling during scheduling"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'tibber': {
                'token': 'test-token',
                'home_id': 'home-123',
                'debug': False
            },
            'shelly': {
                'host': '192.168.1.100',
                'timeout': 10
            },
            'scheduling': {
                'num_cheapest_hours': 3,
                'clear_old_schedules': False
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch('src.schedule_cheapest_hours.ShellyScheduleManager')
    @patch('src.schedule_cheapest_hours.PriceAnalyzer')
    @patch('src.schedule_cheapest_hours.FileManager')
    def test_exception_writes_failure_status(self, mock_file_manager_cls, mock_price_analyzer_cls, mock_shelly_cls):
        """Test exception writes failure status with error message"""
        mock_price_analyzer = mock_price_analyzer_cls.return_value
        mock_price_analyzer.get_cheapest_hours.side_effect = Exception("API connection failed")

        mock_file_manager = mock_file_manager_cls.return_value
        mock_file_manager.file_exists.return_value = False
        mock_file_manager.get_success_file_path.return_value = os.path.join(self.temp_dir, 'success')

        status_file = os.path.join(self.temp_dir, 'status.json')
        status_manager = StatusManager(status_file)
        scheduler = CheapestHoursScheduler(self.config, status_manager=status_manager)
        result = scheduler.run()

        self.assertFalse(result)
        last_run = status_manager.get_last_run()
        self.assertIsNotNone(last_run)
        self.assertEqual(last_run.status, "failure")
        self.assertIn("API connection failed", last_run.error_message)


if __name__ == '__main__':
    unittest.main()
