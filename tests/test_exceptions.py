#!/usr/bin/env python3
"""
Unit tests for custom exceptions
"""

import unittest

from src.exceptions import (
    ShellyTibberError,
    ConfigurationError,
    ConfigFileNotFoundError,
    ConfigValidationError,
    TibberAPIError,
    TibberAuthenticationError,
    TibberDataNotAvailableError,
    TibberHomeNotFoundError,
    ShellyError,
    ShellyConnectionError,
    ShellyTimeoutError,
    ShellyRPCError,
    ScheduleError,
    ScheduleCreationError,
    ScheduleDeletionError,
    NetworkError,
    HTTPRequestError,
    JSONParseError,
)


class TestExceptionHierarchy(unittest.TestCase):
    """Test that exception hierarchy is correct"""

    def test_base_exception(self):
        """Test ShellyTibberError is the base for all custom exceptions"""
        self.assertTrue(issubclass(ConfigurationError, ShellyTibberError))
        self.assertTrue(issubclass(TibberAPIError, ShellyTibberError))
        self.assertTrue(issubclass(ShellyError, ShellyTibberError))
        self.assertTrue(issubclass(ScheduleError, ShellyTibberError))
        self.assertTrue(issubclass(NetworkError, ShellyTibberError))

    def test_configuration_exceptions(self):
        """Test configuration exception hierarchy"""
        self.assertTrue(issubclass(ConfigFileNotFoundError, ConfigurationError))
        self.assertTrue(issubclass(ConfigValidationError, ConfigurationError))

    def test_tibber_exceptions(self):
        """Test Tibber exception hierarchy"""
        self.assertTrue(issubclass(TibberAuthenticationError, TibberAPIError))
        self.assertTrue(issubclass(TibberDataNotAvailableError, TibberAPIError))
        self.assertTrue(issubclass(TibberHomeNotFoundError, TibberAPIError))

    def test_shelly_exceptions(self):
        """Test Shelly exception hierarchy"""
        self.assertTrue(issubclass(ShellyConnectionError, ShellyError))
        self.assertTrue(issubclass(ShellyTimeoutError, ShellyError))
        self.assertTrue(issubclass(ShellyRPCError, ShellyError))

    def test_schedule_exceptions(self):
        """Test schedule exception hierarchy"""
        self.assertTrue(issubclass(ScheduleCreationError, ScheduleError))
        self.assertTrue(issubclass(ScheduleDeletionError, ScheduleError))

    def test_network_exceptions(self):
        """Test network exception hierarchy"""
        self.assertTrue(issubclass(HTTPRequestError, NetworkError))
        self.assertTrue(issubclass(JSONParseError, NetworkError))


class TestExceptionDetails(unittest.TestCase):
    """Test exception message and details handling"""

    def test_base_exception_message(self):
        """Test base exception stores message correctly"""
        exc = ShellyTibberError("Test message")
        self.assertEqual(exc.message, "Test message")
        self.assertEqual(str(exc), "Test message")

    def test_base_exception_with_details(self):
        """Test base exception stores details correctly"""
        details = {"key": "value", "count": 42}
        exc = ShellyTibberError("Test message", details=details)
        self.assertEqual(exc.details, details)
        self.assertIn("key", str(exc))
        self.assertIn("value", str(exc))

    def test_http_request_error_attributes(self):
        """Test HTTPRequestError stores extra attributes"""
        exc = HTTPRequestError(
            "Request failed",
            status_code=404,
            url="https://example.com/api",
            details={"response": "Not Found"}
        )
        self.assertEqual(exc.status_code, 404)
        self.assertEqual(exc.url, "https://example.com/api")
        self.assertEqual(exc.details["response"], "Not Found")

    def test_shelly_rpc_error_attributes(self):
        """Test ShellyRPCError stores extra attributes"""
        exc = ShellyRPCError(
            "RPC failed",
            method="Schedule.Create",
            error_code=-32600,
            details={"error": "Invalid request"}
        )
        self.assertEqual(exc.method, "Schedule.Create")
        self.assertEqual(exc.error_code, -32600)


class TestExceptionCatching(unittest.TestCase):
    """Test that exceptions can be caught at appropriate levels"""

    def test_catch_specific_exception(self):
        """Test catching specific exception type"""
        with self.assertRaises(ConfigFileNotFoundError):
            raise ConfigFileNotFoundError("config.json not found")

    def test_catch_parent_exception(self):
        """Test catching parent exception type"""
        with self.assertRaises(ConfigurationError):
            raise ConfigFileNotFoundError("config.json not found")

    def test_catch_base_exception(self):
        """Test catching base exception type"""
        with self.assertRaises(ShellyTibberError):
            raise TibberDataNotAvailableError("Tomorrow's prices not available")

    def test_catch_builtin_exception(self):
        """Test custom exceptions are also regular Exceptions"""
        with self.assertRaises(Exception):
            raise ShellyConnectionError("Cannot connect")


if __name__ == '__main__':
    unittest.main()
