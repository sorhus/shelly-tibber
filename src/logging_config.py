#!/usr/bin/env python3
"""
Logging Configuration Module
Provides structured logging with JSON output support and consistent formatting
"""

import logging
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs structured JSON logs.
    
    Each log entry includes:
    - timestamp: ISO format timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - logger: Logger name
    - message: Log message
    - correlation_id: Optional ID for tracing a single run
    - Extra fields passed via the 'extra' parameter
    """
    
    def __init__(self, correlation_id: Optional[str] = None):
        super().__init__()
        self.correlation_id = correlation_id
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add correlation ID if set
        if self.correlation_id:
            log_data["correlation_id"] = self.correlation_id
        
        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'message', 'taskName'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                # Ensure value is JSON serializable
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for console output.
    
    Format: TIMESTAMP - LOGGER - LEVEL - MESSAGE [extra_fields]
    """
    
    def __init__(self, include_extras: bool = True):
        super().__init__()
        self.include_extras = include_extras
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build base message
        base_msg = f"{timestamp} - {record.name} - {record.levelname} - {record.getMessage()}"
        
        # Add extra fields if enabled
        if self.include_extras:
            standard_attrs = {
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'taskName'
            }
            
            extras = {}
            for key, value in record.__dict__.items():
                if key not in standard_attrs and not key.startswith('_'):
                    extras[key] = value
            
            if extras:
                extras_str = " ".join(f"{k}={v}" for k, v in extras.items())
                base_msg = f"{base_msg} [{extras_str}]"
        
        # Add exception info if present
        if record.exc_info:
            base_msg = f"{base_msg}\n{self.formatException(record.exc_info)}"
        
        return base_msg


def configure_logging(
    level: str = "INFO",
    json_output: bool = False,
    correlation_id: Optional[str] = None,
    log_file: Optional[str] = None
) -> str:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON formatted logs
        correlation_id: Optional ID for tracing a single run (auto-generated if None)
        log_file: Optional file path to write logs to
        
    Returns:
        The correlation ID being used for this run
    """
    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())[:8]
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    if json_output:
        console_handler.setFormatter(StructuredFormatter(correlation_id))
    else:
        console_handler.setFormatter(ConsoleFormatter())
    
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        # Always use JSON for file output
        file_handler.setFormatter(StructuredFormatter(correlation_id))
        root_logger.addHandler(file_handler)
    
    return correlation_id


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    
    This is a convenience function that ensures consistent logger naming.
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds extra context to all log messages.
    
    Usage:
        logger = LoggerAdapter(get_logger(__name__), {"component": "scheduler"})
        logger.info("Schedule created", extra={"schedule_id": 123})
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        # Merge adapter's extra with call's extra
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def log_operation(
    logger: logging.Logger,
    operation: str,
    **context
) -> None:
    """
    Log an operation with structured context.
    
    Args:
        logger: Logger instance
        operation: Name of the operation being performed
        **context: Additional context fields
    """
    logger.info(operation, extra=context)


def log_success(
    logger: logging.Logger,
    operation: str,
    **context
) -> None:
    """Log successful operation completion."""
    logger.info(f"{operation} completed successfully", extra={"status": "success", **context})


def log_failure(
    logger: logging.Logger,
    operation: str,
    error: Optional[Exception] = None,
    **context
) -> None:
    """Log operation failure."""
    extra = {"status": "failure", **context}
    if error:
        extra["error_type"] = type(error).__name__
        extra["error_message"] = str(error)
    logger.error(f"{operation} failed", extra=extra)
