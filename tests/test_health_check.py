#!/usr/bin/env python3
"""
Unit tests for health check module
"""

import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

from src.health_check import (
    HealthStatus,
    RunStatus,
    HealthCheckResult,
    StatusManager,
    check_health,
    format_health_check,
)


class TestRunStatus(unittest.TestCase):
    """Test RunStatus dataclass"""
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        status = RunStatus(
            timestamp="2026-01-21T10:00:00Z",
            status="success",
            schedules_created=6,
            cheapest_hours=["02:00", "03:00", "04:00"],
            target_date="2026-01-22"
        )
        
        data = status.to_dict()
        
        self.assertEqual(data["timestamp"], "2026-01-21T10:00:00Z")
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["schedules_created"], 6)
        self.assertEqual(data["cheapest_hours"], ["02:00", "03:00", "04:00"])
    
    def test_from_dict(self):
        """Test creation from dictionary"""
        data = {
            "timestamp": "2026-01-21T10:00:00Z",
            "status": "success",
            "schedules_created": 6,
            "target_date": "2026-01-22"
        }
        
        status = RunStatus.from_dict(data)
        
        self.assertEqual(status.timestamp, "2026-01-21T10:00:00Z")
        self.assertEqual(status.status, "success")
        self.assertEqual(status.schedules_created, 6)
    
    def test_from_dict_with_defaults(self):
        """Test creation from partial dictionary"""
        data = {
            "timestamp": "2026-01-21T10:00:00Z",
            "status": "success"
        }
        
        status = RunStatus.from_dict(data)
        
        self.assertEqual(status.schedules_created, 0)
        self.assertEqual(status.cheapest_hours, [])
        self.assertIsNone(status.error_message)


class TestHealthCheckResult(unittest.TestCase):
    """Test HealthCheckResult dataclass"""
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = HealthCheckResult(
            status=HealthStatus.OK,
            message="All good",
            details={"key": "value"}
        )
        
        data = result.to_dict()
        
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["message"], "All good")
        self.assertEqual(data["details"], {"key": "value"})
        self.assertIn("checked_at", data)
    
    def test_to_dict_with_last_run(self):
        """Test conversion includes last_run"""
        last_run = RunStatus(
            timestamp="2026-01-21T10:00:00Z",
            status="success"
        )
        result = HealthCheckResult(
            status=HealthStatus.OK,
            message="All good",
            last_run=last_run
        )
        
        data = result.to_dict()
        
        self.assertIn("last_run", data)
        self.assertEqual(data["last_run"]["status"], "success")


class TestStatusManager(unittest.TestCase):
    """Test StatusManager"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.status_file = os.path.join(self.temp_dir, "status.json")
        self.manager = StatusManager(self.status_file)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_write_and_read_status(self):
        """Test writing and reading status"""
        status = RunStatus(
            timestamp="2026-01-21T10:00:00Z",
            status="success",
            schedules_created=6
        )
        
        self.manager.write_status(status)
        last_run = self.manager.get_last_run()
        
        self.assertIsNotNone(last_run)
        self.assertEqual(last_run.status, "success")
        self.assertEqual(last_run.schedules_created, 6)
    
    def test_get_last_run_no_file(self):
        """Test get_last_run when no file exists"""
        last_run = self.manager.get_last_run()
        self.assertIsNone(last_run)
    
    def test_history_preserved(self):
        """Test that history is preserved"""
        for i in range(3):
            status = RunStatus(
                timestamp=f"2026-01-2{i}T10:00:00Z",
                status="success",
                schedules_created=i
            )
            self.manager.write_status(status)
        
        history = self.manager.get_history()
        
        self.assertEqual(len(history), 3)
        # Most recent first
        self.assertEqual(history[0].schedules_created, 2)
        self.assertEqual(history[2].schedules_created, 0)
    
    def test_history_limited_to_10(self):
        """Test that history is limited to 10 entries"""
        for i in range(15):
            status = RunStatus(
                timestamp=f"2026-01-{i:02d}T10:00:00Z",
                status="success"
            )
            self.manager.write_status(status)
        
        history = self.manager.get_history()
        self.assertEqual(len(history), 10)
    
    def test_creates_directory(self):
        """Test that directory is created if needed"""
        nested_path = os.path.join(self.temp_dir, "nested", "dir", "status.json")
        manager = StatusManager(nested_path)
        
        status = RunStatus(timestamp="2026-01-21T10:00:00Z", status="success")
        manager.write_status(status)
        
        self.assertTrue(os.path.exists(nested_path))


class TestCheckHealth(unittest.TestCase):
    """Test check_health function"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.status_file = os.path.join(self.temp_dir, "status.json")
        self.manager = StatusManager(self.status_file)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_unknown_when_no_status(self):
        """Test UNKNOWN status when no status file"""
        result = check_health(self.manager)
        
        self.assertEqual(result.status, HealthStatus.UNKNOWN)
        self.assertIn("not have run", result.message)
    
    def test_ok_for_recent_success(self):
        """Test OK status for recent successful run"""
        now = datetime.now(timezone.utc)
        status = RunStatus(
            timestamp=now.isoformat(),
            status="success",
            schedules_created=6,
            target_date="2026-01-22"
        )
        self.manager.write_status(status)
        
        result = check_health(self.manager)
        
        self.assertEqual(result.status, HealthStatus.OK)
        self.assertIn("Healthy", result.message)
    
    def test_error_for_failed_run(self):
        """Test ERROR status for failed run"""
        now = datetime.now(timezone.utc)
        status = RunStatus(
            timestamp=now.isoformat(),
            status="failure",
            error_message="Connection refused"
        )
        self.manager.write_status(status)
        
        result = check_health(self.manager)
        
        self.assertEqual(result.status, HealthStatus.ERROR)
        self.assertIn("Connection refused", result.message)
    
    def test_warning_for_stale_run(self):
        """Test WARNING status for stale run"""
        old_time = datetime.now(timezone.utc) - timedelta(hours=30)
        status = RunStatus(
            timestamp=old_time.isoformat(),
            status="success"
        )
        self.manager.write_status(status)
        
        result = check_health(self.manager, max_age_hours=25)
        
        self.assertEqual(result.status, HealthStatus.WARNING)
        self.assertIn("hours ago", result.message)
    
    def test_warning_for_partial_success(self):
        """Test WARNING status for partial success"""
        now = datetime.now(timezone.utc)
        status = RunStatus(
            timestamp=now.isoformat(),
            status="partial"
        )
        self.manager.write_status(status)
        
        result = check_health(self.manager)
        
        self.assertEqual(result.status, HealthStatus.WARNING)
        self.assertIn("warnings", result.message)


class TestFormatHealthCheck(unittest.TestCase):
    """Test format_health_check function"""
    
    def test_basic_format(self):
        """Test basic formatting"""
        result = HealthCheckResult(
            status=HealthStatus.OK,
            message="All systems operational"
        )
        
        output = format_health_check(result)
        
        self.assertIn("OK", output)
        self.assertIn("All systems operational", output)
    
    def test_verbose_format(self):
        """Test verbose formatting"""
        last_run = RunStatus(
            timestamp="2026-01-21T10:00:00Z",
            status="success",
            schedules_created=6,
            target_date="2026-01-22",
            duration_seconds=5.5,
            cheapest_hours=["02:00", "03:00", "04:00"]
        )
        result = HealthCheckResult(
            status=HealthStatus.OK,
            message="Healthy",
            last_run=last_run
        )
        
        output = format_health_check(result, verbose=True)
        
        self.assertIn("Last Run Details", output)
        self.assertIn("2026-01-21T10:00:00Z", output)
        self.assertIn("Schedules Created: 6", output)
        self.assertIn("02:00", output)
    
    def test_dry_run_indicator(self):
        """Test dry run indicator in verbose output"""
        last_run = RunStatus(
            timestamp="2026-01-21T10:00:00Z",
            status="success",
            dry_run=True
        )
        result = HealthCheckResult(
            status=HealthStatus.OK,
            message="Healthy",
            last_run=last_run
        )
        
        output = format_health_check(result, verbose=True)
        
        self.assertIn("DRY RUN", output)


if __name__ == '__main__':
    unittest.main()
