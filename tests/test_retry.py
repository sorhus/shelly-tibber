#!/usr/bin/env python3
"""
Unit tests for retry module
"""

import unittest
from unittest.mock import Mock, patch, call
import time

from src.retry import retry_with_backoff, RetryConfig, execute_with_retry


class TestRetryWithBackoff(unittest.TestCase):
    """Test retry_with_backoff decorator"""

    def test_success_on_first_attempt(self):
        """Test function succeeds on first attempt"""
        mock_func = Mock(return_value="success")
        
        @retry_with_backoff(max_attempts=3)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 1)

    def test_success_after_retry(self):
        """Test function succeeds after retry"""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    def test_failure_after_max_attempts(self):
        """Test function fails after max attempts"""
        mock_func = Mock(side_effect=Exception("always fails"))
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        def test_func():
            return mock_func()
        
        with self.assertRaises(Exception) as context:
            test_func()
        
        self.assertIn("always fails", str(context.exception))
        self.assertEqual(mock_func.call_count, 3)

    def test_only_catches_specified_exceptions(self):
        """Test only specified exceptions trigger retry"""
        mock_func = Mock(side_effect=ValueError("wrong type"))
        
        @retry_with_backoff(max_attempts=3, exceptions=(TypeError,), initial_delay=0.01)
        def test_func():
            return mock_func()
        
        with self.assertRaises(ValueError):
            test_func()
        
        # Should fail immediately without retry since ValueError is not in exceptions
        self.assertEqual(mock_func.call_count, 1)

    def test_catches_specified_exceptions(self):
        """Test specified exceptions trigger retry"""
        mock_func = Mock(side_effect=[TypeError("fail"), "success"])
        
        @retry_with_backoff(max_attempts=3, exceptions=(TypeError,), initial_delay=0.01)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)

    def test_on_retry_callback(self):
        """Test on_retry callback is called"""
        mock_func = Mock(side_effect=[Exception("fail"), "success"])
        on_retry_mock = Mock()
        
        @retry_with_backoff(max_attempts=3, initial_delay=0.01, on_retry=on_retry_mock)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        self.assertEqual(result, "success")
        on_retry_mock.assert_called_once()
        # Check callback was called with (exception, attempt, delay)
        args = on_retry_mock.call_args[0]
        self.assertIsInstance(args[0], Exception)
        self.assertEqual(args[1], 1)  # First attempt


class TestRetryConfig(unittest.TestCase):
    """Test RetryConfig class"""

    def test_default_values(self):
        """Test default configuration values"""
        config = RetryConfig()
        
        self.assertEqual(config.max_attempts, 3)
        self.assertEqual(config.backoff_factor, 2.0)
        self.assertEqual(config.initial_delay, 1.0)
        self.assertEqual(config.max_delay, 60.0)
        self.assertTrue(config.enabled)

    def test_custom_values(self):
        """Test custom configuration values"""
        config = RetryConfig(
            max_attempts=5,
            backoff_factor=1.5,
            initial_delay=0.5,
            max_delay=30.0,
            enabled=False
        )
        
        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.backoff_factor, 1.5)
        self.assertEqual(config.initial_delay, 0.5)
        self.assertEqual(config.max_delay, 30.0)
        self.assertFalse(config.enabled)

    def test_from_dict(self):
        """Test creating config from dictionary"""
        data = {
            'max_attempts': 4,
            'backoff_factor': 3.0,
            'initial_delay': 2.0,
            'max_delay': 120.0,
            'enabled': True
        }
        
        config = RetryConfig.from_dict(data)
        
        self.assertEqual(config.max_attempts, 4)
        self.assertEqual(config.backoff_factor, 3.0)
        self.assertEqual(config.initial_delay, 2.0)
        self.assertEqual(config.max_delay, 120.0)
        self.assertTrue(config.enabled)

    def test_from_dict_with_defaults(self):
        """Test creating config from partial dictionary uses defaults"""
        data = {'max_attempts': 5}
        
        config = RetryConfig.from_dict(data)
        
        self.assertEqual(config.max_attempts, 5)
        self.assertEqual(config.backoff_factor, 2.0)  # default
        self.assertEqual(config.initial_delay, 1.0)  # default

    def test_to_dict(self):
        """Test converting config to dictionary"""
        config = RetryConfig(max_attempts=4, backoff_factor=1.5)
        
        data = config.to_dict()
        
        self.assertEqual(data['max_attempts'], 4)
        self.assertEqual(data['backoff_factor'], 1.5)
        self.assertIn('initial_delay', data)
        self.assertIn('max_delay', data)
        self.assertIn('enabled', data)


class TestExecuteWithRetry(unittest.TestCase):
    """Test execute_with_retry function"""

    def test_disabled_retry(self):
        """Test retry is skipped when disabled"""
        mock_func = Mock(side_effect=Exception("fail"))
        config = RetryConfig(enabled=False)
        
        with self.assertRaises(Exception):
            execute_with_retry(mock_func, config)
        
        # Should only be called once since retry is disabled
        self.assertEqual(mock_func.call_count, 1)

    def test_enabled_retry(self):
        """Test retry works when enabled"""
        mock_func = Mock(side_effect=[Exception("fail"), "success"])
        config = RetryConfig(enabled=True, max_attempts=3, initial_delay=0.01)
        
        result = execute_with_retry(mock_func, config)
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)

    def test_with_specific_exceptions(self):
        """Test retry with specific exception types"""
        mock_func = Mock(side_effect=[ValueError("fail"), "success"])
        config = RetryConfig(enabled=True, max_attempts=3, initial_delay=0.01)
        
        result = execute_with_retry(mock_func, config, exceptions=(ValueError,))
        
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)


if __name__ == '__main__':
    unittest.main()
