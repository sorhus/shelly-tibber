#!/usr/bin/env python3
"""
Unit tests for Shelly schedule module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.shelly_schedule import ShellyScheduleManager, ScheduleJob
from src.exceptions import ShellyConnectionError


class TestShellyScheduleManagerInit(unittest.TestCase):
    """Test ShellyScheduleManager initialization"""

    def test_init_stores_config(self):
        """Test manager stores configuration"""
        manager = ShellyScheduleManager(
            shelly_host="192.168.1.100",
            timeout=15,
            debug=True
        )
        
        self.assertEqual(manager.shelly_host, "192.168.1.100")
        self.assertEqual(manager.timeout, 15)
        self.assertTrue(manager.debug)
        self.assertEqual(manager.base_url, "http://192.168.1.100/rpc")


class TestScheduleJob(unittest.TestCase):
    """Test ScheduleJob dataclass"""

    def test_default_values(self):
        """Test ScheduleJob default values"""
        job = ScheduleJob()
        
        self.assertIsNone(job.id)
        self.assertTrue(job.enable)
        self.assertEqual(job.timespec, "")
        self.assertEqual(job.calls, [])

    def test_with_values(self):
        """Test ScheduleJob with values"""
        calls = [{"method": "Switch.Set", "params": {"on": True}}]
        job = ScheduleJob(
            id=123,
            enable=False,
            timespec="0 0 10 * * 1",
            calls=calls
        )
        
        self.assertEqual(job.id, 123)
        self.assertFalse(job.enable)
        self.assertEqual(job.timespec, "0 0 10 * * 1")
        self.assertEqual(job.calls, calls)


class TestCreateSwitchSchedule(unittest.TestCase):
    """Test switch schedule creation"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_create_switch_schedule_on(self):
        """Test creating ON schedule"""
        with patch.object(self.manager, 'create_schedule', return_value=1) as mock_create:
            schedule_id = self.manager.create_switch_schedule(
                hour=10,
                minute=30,
                switch_id=0,
                turn_on=True
            )
        
        self.assertEqual(schedule_id, 1)
        mock_create.assert_called_once()
        args = mock_create.call_args
        self.assertIn("10", args[0][0])  # timespec contains hour
        self.assertIn("30", args[0][0])  # timespec contains minute
        self.assertTrue(args[0][1][0]["params"]["on"])  # turn_on=True

    def test_create_switch_schedule_off(self):
        """Test creating OFF schedule"""
        with patch.object(self.manager, 'create_schedule', return_value=2) as mock_create:
            schedule_id = self.manager.create_switch_schedule(
                hour=14,
                minute=0,
                switch_id=0,
                turn_on=False
            )
        
        self.assertEqual(schedule_id, 2)
        args = mock_create.call_args
        self.assertFalse(args[0][1][0]["params"]["on"])  # turn_on=False

    def test_create_switch_schedule_with_weekdays(self):
        """Test creating schedule with specific weekdays"""
        with patch.object(self.manager, 'create_schedule', return_value=3) as mock_create:
            schedule_id = self.manager.create_switch_schedule(
                hour=10,
                minute=0,
                switch_id=0,
                turn_on=True,
                weekdays=[1, 2, 3]  # Mon, Tue, Wed
            )
        
        args = mock_create.call_args
        timespec = args[0][0]
        self.assertIn("1,2,3", timespec)


class TestDeleteSchedulesForWeekdays(unittest.TestCase):
    """Test deleting schedules by weekday"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_delete_schedules_for_weekdays(self):
        """Test deleting schedules for specific weekdays"""
        # Mock existing schedules
        schedules = [
            ScheduleJob(id=1, timespec="0 0 10 * * 1"),  # Monday
            ScheduleJob(id=2, timespec="0 0 11 * * 2"),  # Tuesday
            ScheduleJob(id=3, timespec="0 0 12 * * 3"),  # Wednesday
        ]
        
        with patch.object(self.manager, 'list_schedules', return_value=schedules):
            with patch.object(self.manager, 'delete_schedule') as mock_delete:
                deleted = self.manager.delete_schedules_for_weekdays([1, 2])  # Mon, Tue
        
        self.assertEqual(deleted, 2)
        self.assertEqual(mock_delete.call_count, 2)

    def test_delete_schedules_no_matches(self):
        """Test deleting when no schedules match"""
        schedules = [
            ScheduleJob(id=1, timespec="0 0 10 * * 5"),  # Friday
            ScheduleJob(id=2, timespec="0 0 11 * * 6"),  # Saturday
        ]
        
        with patch.object(self.manager, 'list_schedules', return_value=schedules):
            with patch.object(self.manager, 'delete_schedule') as mock_delete:
                deleted = self.manager.delete_schedules_for_weekdays([1, 2])  # Mon, Tue
        
        self.assertEqual(deleted, 0)
        mock_delete.assert_not_called()


class TestCreatePriceBasedSchedules(unittest.TestCase):
    """Test price-based schedule creation"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_empty_price_points(self):
        """Test with empty price points"""
        schedule_ids, blocks = self.manager.create_price_based_schedules([])
        
        self.assertEqual(schedule_ids, [])
        self.assertEqual(blocks, [])

    def test_single_price_point(self):
        """Test with single price point"""
        price_points = [
            {"startsAt": "2024-01-15T10:00:00Z", "total": 0.5}
        ]
        
        with patch.object(self.manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2]
            
            schedule_ids, blocks = self.manager.create_price_based_schedules(price_points)
        
        self.assertEqual(len(schedule_ids), 2)  # ON and OFF
        self.assertEqual(len(blocks), 1)

    def test_consecutive_hours_merged(self):
        """Test consecutive hours are merged into one block"""
        price_points = [
            {"startsAt": "2024-01-15T10:00:00Z", "total": 0.5},
            {"startsAt": "2024-01-15T11:00:00Z", "total": 0.4},
            {"startsAt": "2024-01-15T12:00:00Z", "total": 0.6},
        ]
        
        with patch.object(self.manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2]  # Just ON and OFF for one block
            
            schedule_ids, blocks = self.manager.create_price_based_schedules(price_points)
        
        self.assertEqual(len(blocks), 1)  # All consecutive = 1 block
        self.assertEqual(mock_create.call_count, 2)  # ON at 10:00, OFF at 13:00

    def test_non_consecutive_hours_separate_blocks(self):
        """Test non-consecutive hours create separate blocks"""
        price_points = [
            {"startsAt": "2024-01-15T10:00:00Z", "total": 0.5},
            {"startsAt": "2024-01-15T14:00:00Z", "total": 0.4},  # Gap
        ]
        
        with patch.object(self.manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2, 3, 4]
            
            schedule_ids, blocks = self.manager.create_price_based_schedules(price_points)
        
        self.assertEqual(len(blocks), 2)  # 2 separate blocks
        self.assertEqual(mock_create.call_count, 4)  # ON/OFF for each block

    def test_unsorted_price_points_sorted(self):
        """Test price points are sorted by time"""
        price_points = [
            {"startsAt": "2024-01-15T12:00:00Z", "total": 0.6},
            {"startsAt": "2024-01-15T10:00:00Z", "total": 0.5},  # Earlier
            {"startsAt": "2024-01-15T11:00:00Z", "total": 0.4},
        ]
        
        with patch.object(self.manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2]
            
            schedule_ids, blocks = self.manager.create_price_based_schedules(price_points)
        
        # Should be sorted and merged into one block
        self.assertEqual(len(blocks), 1)
        # Block should start at 10:00 (earliest)
        self.assertEqual(blocks[0][0].hour, 10)


class TestTestConnection(unittest.TestCase):
    """Test connection testing"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_connection_success(self):
        """Test successful connection"""
        with patch.object(self.manager, '_make_request') as mock_request:
            mock_request.return_value = {
                "model": "ShellyPro1",
                "version": "1.0.0"
            }
            
            result = self.manager.test_connection()
        
        self.assertTrue(result)

    def test_connection_failure(self):
        """Test failed connection"""
        with patch.object(self.manager, '_make_request') as mock_request:
            mock_request.side_effect = ShellyConnectionError("Connection refused")
            
            result = self.manager.test_connection()
        
        self.assertFalse(result)


class TestListSchedules(unittest.TestCase):
    """Test listing schedules"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_list_schedules_parses_response(self):
        """Test list_schedules correctly parses RPC response"""
        mock_response = {
            "result": {
                "jobs": [
                    {
                        "id": 1,
                        "enable": True,
                        "timespec": "0 0 10 * * 1",
                        "calls": [{"method": "Switch.Set", "params": {"on": True}}]
                    },
                    {
                        "id": 2,
                        "enable": False,
                        "timespec": "0 30 14 * * 2",
                        "calls": [{"method": "Switch.Set", "params": {"on": False}}]
                    }
                ]
            }
        }

        with patch.object(self.manager, '_make_request', return_value=mock_response):
            schedules = self.manager.list_schedules()

        self.assertEqual(len(schedules), 2)
        self.assertEqual(schedules[0].id, 1)
        self.assertTrue(schedules[0].enable)
        self.assertEqual(schedules[0].timespec, "0 0 10 * * 1")
        self.assertEqual(schedules[1].id, 2)
        self.assertFalse(schedules[1].enable)

    def test_list_schedules_empty_response(self):
        """Test list_schedules handles empty jobs list"""
        mock_response = {"result": {"jobs": []}}

        with patch.object(self.manager, '_make_request', return_value=mock_response):
            schedules = self.manager.list_schedules()

        self.assertEqual(schedules, [])


class TestUpdateSchedule(unittest.TestCase):
    """Test schedule updates"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_update_schedule(self):
        """Test updating a schedule"""
        mock_response = {"rev": 5}

        with patch.object(self.manager, '_make_request', return_value=mock_response) as mock_request:
            revision = self.manager.update_schedule(123, enable=False, timespec="0 0 11 * * 1")

        self.assertEqual(revision, 5)
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "Schedule.Update")
        self.assertEqual(call_args[0][1]["id"], 123)
        self.assertFalse(call_args[0][1]["enable"])


class TestMakeRequest(unittest.TestCase):
    """Test _make_request error handling"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_timeout_raises_shelly_timeout_error(self):
        """Test timeout raises ShellyTimeoutError"""
        from src.exceptions import ShellyTimeoutError
        import requests

        with patch('src.shelly_schedule.requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout()

            with self.assertRaises(ShellyTimeoutError):
                self.manager._make_request_internal("Test.Method")

    def test_connection_error_raises_shelly_connection_error(self):
        """Test connection error raises ShellyConnectionError"""
        import requests

        with patch('src.shelly_schedule.requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError()

            with self.assertRaises(ShellyConnectionError):
                self.manager._make_request_internal("Test.Method")

    def test_rpc_error_raises_shelly_rpc_error(self):
        """Test RPC error in response raises ShellyRPCError"""
        from src.exceptions import ShellyRPCError

        mock_response = Mock()
        mock_response.json.return_value = {
            "error": {"code": -1, "message": "Method not found"}
        }

        with patch('src.shelly_schedule.requests.post', return_value=mock_response):
            with self.assertRaises(ShellyRPCError):
                self.manager._make_request_internal("Invalid.Method")

    def test_successful_request_returns_result(self):
        """Test successful request returns result"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {"id": 123}
        }

        with patch('src.shelly_schedule.requests.post', return_value=mock_response):
            result = self.manager._make_request_internal("Schedule.Create", {"timespec": "0 0 10 * * *"})

        # Should return params if present, otherwise the full result
        self.assertIsNotNone(result)


class TestCreateSchedule(unittest.TestCase):
    """Test schedule creation"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_create_schedule_returns_id(self):
        """Test create_schedule returns the schedule ID"""
        mock_response = {"result": {"id": 456}}

        with patch.object(self.manager, '_make_request', return_value=mock_response):
            schedule_id = self.manager.create_schedule(
                timespec="0 0 10 * * 1",
                calls=[{"method": "Switch.Set", "params": {"on": True}}]
            )

        self.assertEqual(schedule_id, 456)

    def test_create_schedule_error_raises_schedule_creation_error(self):
        """Test create_schedule raises ScheduleCreationError on failure"""
        from src.exceptions import ScheduleCreationError

        with patch.object(self.manager, '_make_request', side_effect=ShellyConnectionError("Connection failed")):
            with self.assertRaises(ScheduleCreationError):
                self.manager.create_schedule(
                    timespec="0 0 10 * * 1",
                    calls=[{"method": "Switch.Set", "params": {"on": True}}]
                )


class TestDeleteSchedule(unittest.TestCase):
    """Test schedule deletion"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_delete_schedule_returns_revision(self):
        """Test delete_schedule returns revision"""
        mock_response = {"rev": 10}

        with patch.object(self.manager, '_make_request', return_value=mock_response):
            revision = self.manager.delete_schedule(123)

        self.assertEqual(revision, 10)

    def test_delete_schedule_error_raises_schedule_deletion_error(self):
        """Test delete_schedule raises ScheduleDeletionError on failure"""
        from src.exceptions import ScheduleDeletionError

        with patch.object(self.manager, '_make_request', side_effect=ShellyConnectionError("Connection failed")):
            with self.assertRaises(ScheduleDeletionError):
                self.manager.delete_schedule(123)


class TestDeleteAllSchedules(unittest.TestCase):
    """Test delete all schedules"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False)
        self.manager.logger = Mock()

    def test_delete_all_schedules_returns_revision(self):
        """Test delete_all_schedules returns revision"""
        mock_response = {"rev": 15}

        with patch.object(self.manager, '_make_request', return_value=mock_response):
            revision = self.manager.delete_all_schedules()

        self.assertEqual(revision, 15)

    def test_delete_all_schedules_error_raises_schedule_deletion_error(self):
        """Test delete_all_schedules raises ScheduleDeletionError on failure"""
        from src.exceptions import ScheduleDeletionError

        with patch.object(self.manager, '_make_request', side_effect=ShellyConnectionError("Connection failed")):
            with self.assertRaises(ScheduleDeletionError):
                self.manager.delete_all_schedules()


class TestDryRunMode(unittest.TestCase):
    """Test dry-run mode functionality"""

    def setUp(self):
        self.manager = ShellyScheduleManager("192.168.1.100", debug=False, dry_run=True)
        self.manager.logger = Mock()

    def test_dry_run_init(self):
        """Test dry-run mode is stored"""
        self.assertTrue(self.manager.dry_run)

    def test_dry_run_list_schedules_returns_empty(self):
        """Test list_schedules returns empty list in dry-run mode"""
        result = self.manager.list_schedules()
        self.assertEqual(result, [])

    def test_dry_run_create_schedule_returns_fake_id(self):
        """Test create_schedule returns fake IDs in dry-run mode"""
        id1 = self.manager.create_schedule("0 0 10 * * 1", [{"method": "Switch.Set", "params": {"on": True}}])
        id2 = self.manager.create_schedule("0 0 11 * * 1", [{"method": "Switch.Set", "params": {"on": False}}])
        
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)

    def test_dry_run_delete_schedule_succeeds(self):
        """Test delete_schedule succeeds in dry-run mode"""
        result = self.manager.delete_schedule(123)
        self.assertEqual(result, 0)

    def test_dry_run_delete_all_schedules_succeeds(self):
        """Test delete_all_schedules succeeds in dry-run mode"""
        result = self.manager.delete_all_schedules()
        self.assertEqual(result, 0)

    def test_dry_run_test_connection_returns_true(self):
        """Test test_connection returns True in dry-run mode without making request"""
        result = self.manager.test_connection()
        self.assertTrue(result)

    def test_dry_run_no_http_requests(self):
        """Test no HTTP requests are made in dry-run mode"""
        with patch('src.shelly_schedule.requests.post') as mock_post:
            self.manager.list_schedules()
            self.manager.create_schedule("0 0 10 * * 1", [])
            self.manager.delete_schedule(1)
            self.manager.delete_all_schedules()
            self.manager.test_connection()
            
            mock_post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
