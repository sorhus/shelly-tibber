#!/usr/bin/env python3
"""
Unit tests for file I/O module
"""

import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta

from src.file_io import FileManager


class TestFileManager(unittest.TestCase):
    """Test FileManager class"""

    def setUp(self):
        """Create temporary directory for tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.file_manager = FileManager(base_output_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_get_daily_dir_creates_directory(self):
        """Test daily directory is created"""
        date = "2024-01-15"
        daily_dir = self.file_manager._get_daily_dir(date)
        
        self.assertTrue(os.path.exists(daily_dir))
        self.assertTrue(os.path.isdir(daily_dir))
        self.assertIn(date, daily_dir)

    def test_write_result_file(self):
        """Test writing result file"""
        date = "2024-01-15"
        data = {"test": "data", "count": 42}
        
        filepath = self.file_manager.write_result_file(date, data)
        
        self.assertTrue(os.path.exists(filepath))
        with open(filepath) as f:
            loaded = json.load(f)
        self.assertEqual(loaded["test"], "data")
        self.assertEqual(loaded["count"], 42)

    def test_read_result_file(self):
        """Test reading result file"""
        date = "2024-01-15"
        data = {"test": "data", "count": 42}
        
        # Write first
        self.file_manager.write_result_file(date, data)
        
        # Then read
        loaded = self.file_manager.read_result_file(date)
        
        self.assertEqual(loaded["test"], "data")
        self.assertEqual(loaded["count"], 42)

    def test_read_result_file_not_found(self):
        """Test reading non-existent result file returns empty dict"""
        date = "2024-01-15"
        
        result = self.file_manager.read_result_file(date)
        
        self.assertEqual(result, {})

    def test_file_exists(self):
        """Test file existence check"""
        date = "2024-01-15"
        data = {"test": "data"}
        
        filepath = self.file_manager.write_result_file(date, data)
        
        self.assertTrue(self.file_manager.file_exists(filepath))
        self.assertFalse(self.file_manager.file_exists("/nonexistent/path"))

    def test_write_success_file(self):
        """Test writing success file"""
        date = "2024-01-15"
        
        filepath = self.file_manager.write_success_file(date)
        
        self.assertTrue(os.path.exists(filepath))
        self.assertIn("success_", filepath)
        
        with open(filepath) as f:
            content = f.read()
        self.assertIn("Successfully processed", content)

    def test_get_success_file_path(self):
        """Test success file path generation"""
        date = "2024-01-15"
        
        path = self.file_manager.get_success_file_path(date)
        
        self.assertIn(date, path)
        self.assertIn("success_", path)

    def test_replace_result_file(self):
        """Test replacing result file"""
        date = "2024-01-15"
        original_data = {"version": 1}
        new_data = {"version": 2}
        
        self.file_manager.write_result_file(date, original_data)
        self.file_manager.replace_result_file(date, new_data)
        
        loaded = self.file_manager.read_result_file(date)
        self.assertEqual(loaded["version"], 2)


class TestFileManagerCleanup(unittest.TestCase):
    """Test FileManager cleanup functionality"""

    def setUp(self):
        """Create temporary directory for tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.file_manager = FileManager(base_output_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_cleanup_old_files(self):
        """Test cleanup removes old directories"""
        today = datetime.now()
        
        # Create directories for different dates
        old_date = (today - timedelta(days=10)).strftime('%Y-%m-%d')
        recent_date = (today - timedelta(days=3)).strftime('%Y-%m-%d')
        
        old_dir = os.path.join(self.temp_dir, old_date)
        recent_dir = os.path.join(self.temp_dir, recent_date)
        
        os.makedirs(old_dir)
        os.makedirs(recent_dir)
        
        # Create dummy files
        with open(os.path.join(old_dir, "test.txt"), 'w') as f:
            f.write("old")
        with open(os.path.join(recent_dir, "test.txt"), 'w') as f:
            f.write("recent")
        
        # Cleanup with 7 days retention
        deleted = self.file_manager.cleanup_old_files(days_to_keep=7)
        
        self.assertEqual(deleted, 1)
        self.assertFalse(os.path.exists(old_dir))
        self.assertTrue(os.path.exists(recent_dir))

    def test_cleanup_ignores_non_date_directories(self):
        """Test cleanup ignores directories that aren't dates"""
        # Create non-date directory
        other_dir = os.path.join(self.temp_dir, "not-a-date")
        os.makedirs(other_dir)
        
        deleted = self.file_manager.cleanup_old_files(days_to_keep=7)
        
        self.assertEqual(deleted, 0)
        self.assertTrue(os.path.exists(other_dir))

    def test_cleanup_empty_directory(self):
        """Test cleanup handles empty base directory"""
        deleted = self.file_manager.cleanup_old_files(days_to_keep=7)
        
        self.assertEqual(deleted, 0)


if __name__ == '__main__':
    unittest.main()
