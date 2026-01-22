#!/usr/bin/env python3
"""
Retry Utility Module
Provides retry logic with exponential backoff for network operations
"""

import time
import logging
import functools
from typing import Callable, Type, Tuple, Optional, Any

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
) -> Callable:
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts (including the first one)
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry on
        on_retry: Optional callback called on each retry with (exception, attempt, delay)
    
    Returns:
        Decorated function
    
    Example:
        @retry_with_backoff(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
        def fetch_data():
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.warning(
                            f"{func.__name__} failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise
                    
                    # Calculate delay with cap
                    actual_delay = min(delay, max_delay)
                    
                    logger.info(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {str(e)}. "
                        f"Retrying in {actual_delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt, actual_delay)
                    
                    time.sleep(actual_delay)
                    delay *= backoff_factor
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        enabled: bool = True
    ):
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.enabled = enabled
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RetryConfig':
        """Create RetryConfig from dictionary"""
        return cls(
            max_attempts=data.get('max_attempts', 3),
            backoff_factor=data.get('backoff_factor', 2.0),
            initial_delay=data.get('initial_delay', 1.0),
            max_delay=data.get('max_delay', 60.0),
            enabled=data.get('enabled', True)
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'max_attempts': self.max_attempts,
            'backoff_factor': self.backoff_factor,
            'initial_delay': self.initial_delay,
            'max_delay': self.max_delay,
            'enabled': self.enabled
        }


def execute_with_retry(
    func: Callable,
    retry_config: RetryConfig,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    *args,
    **kwargs
) -> Any:
    """
    Execute a function with retry logic based on RetryConfig.
    
    Args:
        func: Function to execute
        retry_config: Retry configuration
        exceptions: Tuple of exception types to catch and retry on
        *args: Arguments to pass to func
        **kwargs: Keyword arguments to pass to func
    
    Returns:
        Result of func
    """
    if not retry_config.enabled:
        return func(*args, **kwargs)
    
    # Get function name safely (handles Mock objects)
    func_name = getattr(func, '__name__', str(func))
    
    last_exception = None
    delay = retry_config.initial_delay
    
    for attempt in range(1, retry_config.max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            
            if attempt == retry_config.max_attempts:
                logger.warning(
                    f"{func_name} failed after {retry_config.max_attempts} attempts: {str(e)}"
                )
                raise
            
            actual_delay = min(delay, retry_config.max_delay)
            
            logger.info(
                f"{func_name} attempt {attempt}/{retry_config.max_attempts} failed: {str(e)}. "
                f"Retrying in {actual_delay:.1f}s..."
            )
            
            time.sleep(actual_delay)
            delay *= retry_config.backoff_factor
    
    if last_exception:
        raise last_exception
