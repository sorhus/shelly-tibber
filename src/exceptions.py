#!/usr/bin/env python3
"""
Custom Exception Hierarchy
Provides specific exception types for different failure modes
"""


class ShellyTibberError(Exception):
    """Base exception for all application errors"""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# Configuration Errors
class ConfigurationError(ShellyTibberError):
    """Configuration file missing or invalid"""
    pass


class ConfigFileNotFoundError(ConfigurationError):
    """Configuration file does not exist"""
    pass


class ConfigValidationError(ConfigurationError):
    """Configuration values are invalid or missing"""
    pass


# Tibber API Errors
class TibberAPIError(ShellyTibberError):
    """Base class for Tibber API errors"""
    pass


class TibberAuthenticationError(TibberAPIError):
    """Tibber API authentication failed (invalid token)"""
    pass


class TibberRateLimitError(TibberAPIError):
    """Tibber API rate limit exceeded"""
    pass


class TibberDataNotAvailableError(TibberAPIError):
    """Tibber price data not available (e.g., tomorrow's prices not published yet)"""
    pass


class TibberHomeNotFoundError(TibberAPIError):
    """Specified home ID not found in Tibber account"""
    pass


# Shelly Device Errors
class ShellyError(ShellyTibberError):
    """Base class for Shelly device errors"""
    pass


class ShellyConnectionError(ShellyError):
    """Cannot connect to Shelly device"""
    pass


class ShellyTimeoutError(ShellyError):
    """Shelly device request timed out"""
    pass


class ShellyRPCError(ShellyError):
    """Shelly RPC call returned an error"""

    def __init__(self, message: str, method: str = None, error_code: int = None, details: dict = None):
        super().__init__(message, details)
        self.method = method
        self.error_code = error_code


# Schedule Errors
class ScheduleError(ShellyTibberError):
    """Base class for scheduling errors"""
    pass


class ScheduleCreationError(ScheduleError):
    """Failed to create a schedule on the device"""
    pass


class ScheduleDeletionError(ScheduleError):
    """Failed to delete a schedule from the device"""
    pass


class ScheduleConflictError(ScheduleError):
    """Schedule conflicts with existing schedule"""
    pass


# Network Errors
class NetworkError(ShellyTibberError):
    """Base class for network-related errors"""
    pass


class HTTPRequestError(NetworkError):
    """HTTP request failed"""

    def __init__(self, message: str, status_code: int = None, url: str = None, details: dict = None):
        super().__init__(message, details)
        self.status_code = status_code
        self.url = url


class JSONParseError(NetworkError):
    """Failed to parse JSON response"""
    pass
