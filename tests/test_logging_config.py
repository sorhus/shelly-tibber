#!/usr/bin/env python3
"""
Unit tests for logging configuration module
"""

import unittest
import logging
import json
import io
import sys
from unittest.mock import patch

from src.logging_config import (
    StructuredFormatter,
    ConsoleFormatter,
    configure_logging,
    get_logger,
    LoggerAdapter,
    log_operation,
    log_success,
    log_failure,
)


class TestStructuredFormatter(unittest.TestCase):
    """Test StructuredFormatter"""
    
    def setUp(self):
        self.formatter = StructuredFormatter(correlation_id="test-123")
        self.logger = logging.getLogger("test_structured")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
    
    def test_basic_format(self):
        """Test basic log formatting"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = self.formatter.format(record)
        data = json.loads(output)
        
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test")
        self.assertEqual(data["message"], "Test message")
        self.assertEqual(data["correlation_id"], "test-123")
        self.assertIn("timestamp", data)
    
    def test_extra_fields(self):
        """Test extra fields are included"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.schedule_id = 123
        record.action = "create"
        
        output = self.formatter.format(record)
        data = json.loads(output)
        
        self.assertEqual(data["schedule_id"], 123)
        self.assertEqual(data["action"], "create")
    
    def test_without_correlation_id(self):
        """Test formatter without correlation ID"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        self.assertNotIn("correlation_id", data)


class TestConsoleFormatter(unittest.TestCase):
    """Test ConsoleFormatter"""
    
    def test_basic_format(self):
        """Test basic console formatting"""
        formatter = ConsoleFormatter(include_extras=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        self.assertIn("test", output)
        self.assertIn("INFO", output)
        self.assertIn("Test message", output)
    
    def test_with_extras(self):
        """Test console formatting with extra fields"""
        formatter = ConsoleFormatter(include_extras=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.schedule_id = 123
        
        output = formatter.format(record)
        
        self.assertIn("schedule_id=123", output)


class TestConfigureLogging(unittest.TestCase):
    """Test configure_logging function"""
    
    def tearDown(self):
        # Clean up root logger handlers
        logging.getLogger().handlers.clear()
    
    def test_returns_correlation_id(self):
        """Test that configure_logging returns a correlation ID"""
        correlation_id = configure_logging()
        self.assertIsNotNone(correlation_id)
        self.assertEqual(len(correlation_id), 8)
    
    def test_uses_provided_correlation_id(self):
        """Test that provided correlation ID is used"""
        correlation_id = configure_logging(correlation_id="my-id-123")
        self.assertEqual(correlation_id, "my-id-123")
    
    def test_sets_log_level(self):
        """Test that log level is set correctly"""
        configure_logging(level="DEBUG")
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.DEBUG)
    
    def test_json_output_uses_structured_formatter(self):
        """Test that JSON output uses StructuredFormatter"""
        configure_logging(json_output=True)
        root_logger = logging.getLogger()
        
        self.assertEqual(len(root_logger.handlers), 1)
        self.assertIsInstance(root_logger.handlers[0].formatter, StructuredFormatter)
    
    def test_console_output_uses_console_formatter(self):
        """Test that console output uses ConsoleFormatter"""
        configure_logging(json_output=False)
        root_logger = logging.getLogger()
        
        self.assertEqual(len(root_logger.handlers), 1)
        self.assertIsInstance(root_logger.handlers[0].formatter, ConsoleFormatter)


class TestGetLogger(unittest.TestCase):
    """Test get_logger function"""
    
    def test_returns_logger(self):
        """Test that get_logger returns a logger"""
        logger = get_logger("test_module")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test_module")


class TestLoggerAdapter(unittest.TestCase):
    """Test LoggerAdapter"""
    
    def setUp(self):
        self.logger = logging.getLogger("test_adapter")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def test_adds_extra_context(self):
        """Test that adapter adds extra context"""
        adapter = LoggerAdapter(self.logger, {"component": "scheduler"})
        adapter.info("Test message")
        
        output = self.stream.getvalue()
        data = json.loads(output.strip())
        
        self.assertEqual(data["component"], "scheduler")
    
    def test_merges_extra_context(self):
        """Test that adapter merges extra context"""
        adapter = LoggerAdapter(self.logger, {"component": "scheduler"})
        adapter.info("Test message", extra={"schedule_id": 123})
        
        output = self.stream.getvalue()
        data = json.loads(output.strip())
        
        self.assertEqual(data["component"], "scheduler")
        self.assertEqual(data["schedule_id"], 123)


class TestLogHelpers(unittest.TestCase):
    """Test log helper functions"""
    
    def setUp(self):
        self.logger = logging.getLogger("test_helpers")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def test_log_operation(self):
        """Test log_operation function"""
        log_operation(self.logger, "create_schedule", schedule_id=123, weekday=2)
        
        output = self.stream.getvalue()
        data = json.loads(output.strip())
        
        self.assertEqual(data["message"], "create_schedule")
        self.assertEqual(data["schedule_id"], 123)
        self.assertEqual(data["weekday"], 2)
    
    def test_log_success(self):
        """Test log_success function"""
        log_success(self.logger, "create_schedule", schedule_id=123)
        
        output = self.stream.getvalue()
        data = json.loads(output.strip())
        
        self.assertIn("completed successfully", data["message"])
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["schedule_id"], 123)
    
    def test_log_failure(self):
        """Test log_failure function"""
        error = ValueError("Invalid value")
        log_failure(self.logger, "create_schedule", error=error, schedule_id=123)
        
        output = self.stream.getvalue()
        data = json.loads(output.strip())
        
        self.assertIn("failed", data["message"])
        self.assertEqual(data["status"], "failure")
        self.assertEqual(data["error_type"], "ValueError")
        self.assertEqual(data["error_message"], "Invalid value")
        self.assertEqual(data["schedule_id"], 123)
    
    def test_log_failure_without_error(self):
        """Test log_failure without exception"""
        log_failure(self.logger, "create_schedule", schedule_id=123)
        
        output = self.stream.getvalue()
        data = json.loads(output.strip())
        
        self.assertEqual(data["status"], "failure")
        self.assertNotIn("error_type", data)


if __name__ == '__main__':
    unittest.main()
