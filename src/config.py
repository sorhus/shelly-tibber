#!/usr/bin/env python3
"""
Configuration Management Module
Handles loading configuration from config.json file with validation
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

from src.models import AppConfig

from src.exceptions import (
    ConfigFileNotFoundError,
    ConfigValidationError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

# Environment variable mappings (ENV_VAR -> config path)
ENV_VAR_MAPPINGS = {
    "TIBBER_TOKEN": ("tibber", "token"),
    "TIBBER_HOME_ID": ("tibber", "home_id"),
    "TIBBER_DEBUG": ("tibber", "debug"),
    "SHELLY_HOST": ("shelly", "host"),
    "SHELLY_TIMEOUT": ("shelly", "timeout"),
    "SHELLY_USERNAME": ("shelly", "username"),
    "SHELLY_PASSWORD": ("shelly", "password"),
    "NUM_CHEAPEST_HOURS": ("scheduling", "num_cheapest_hours"),
    "CLEAR_OLD_SCHEDULES": ("scheduling", "clear_old_schedules"),
}

# Placeholder values that indicate unconfigured settings
PLACEHOLDER_VALUES = {
    "YOUR_TIBBER_API_TOKEN_HERE",
    "YOUR_TIBBER_HOME_ID_HERE",
    "YOUR_SHELLY_IP_HERE",
}


def _parse_env_value(value: str, field_path: tuple) -> Any:
    """Parse environment variable string to the appropriate type"""
    section, field = field_path
    
    # Boolean fields
    if field in ("debug", "clear_old_schedules"):
        return value.lower() in ("true", "1", "yes", "on")
    
    # Integer fields
    if field in ("timeout", "num_cheapest_hours"):
        try:
            return int(value)
        except ValueError:
            raise ConfigValidationError(
                f"Invalid integer value for {section}.{field}: {value}"
            )
    
    return value


def apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Environment variables take precedence over config file values.
    Supported variables: TIBBER_TOKEN, TIBBER_HOME_ID, SHELLY_HOST, etc.
    """
    for env_var, config_path in ENV_VAR_MAPPINGS.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            section, field = config_path
            
            if section not in config:
                config[section] = {}
            
            parsed_value = _parse_env_value(env_value, config_path)
            config[section][field] = parsed_value
            logger.debug(f"Applied environment override: {env_var} -> {section}.{field}")
    
    return config


def load_config_dict() -> Dict[str, Any]:
    """
    Load configuration from config.json file as a dictionary
    """
    config_file = 'config.json'
    
    if not os.path.exists(config_file):
        raise ConfigFileNotFoundError(
            f"Configuration file not found: {config_file}",
            details={"path": config_file}
        )
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_file}")
        return config
    except json.JSONDecodeError as e:
        raise ConfigurationError(
            f"Invalid JSON in config file: {config_file}",
            details={"path": config_file, "error": str(e)}
        )
    except IOError as e:
        raise ConfigurationError(
            f"Failed to read config file: {config_file}",
            details={"path": config_file, "error": str(e)}
        )


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json file
    
    Deprecated: Use load_config_dict() or get_typed_config() instead
    """
    return load_config_dict()

def apply_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply sane defaults for missing configuration values
    """
    defaults = {
        'tibber': {
            'debug': False
        },
        'shelly': {
            'timeout': 10,
            'username': '',
            'password': ''
        },
        'scheduling': {
            'num_cheapest_hours': 10
        }
    }
    
    # Apply defaults recursively
    for section, section_defaults in defaults.items():
        if section not in config:
            config[section] = {}
        
        for key, default_value in section_defaults.items():
            if key not in config[section] or config[section][key] is None:
                config[section][key] = default_value
                logger.debug(f"Applied default for {section}.{key}: {default_value}")
    
    return config

def validate_config(config: Dict[str, Any], require_home_id: bool = True) -> None:
    """
    Validate configuration values.
    
    Checks for:
    - Required fields (tibber.token, tibber.home_id if required)
    - Placeholder values that haven't been configured
    - Basic type validation
    """
    errors: List[str] = []
    
    # Check required fields
    required_fields = [('tibber', 'token')]
    if require_home_id:
        required_fields.append(('tibber', 'home_id'))
    
    for section, field in required_fields:
        value = config.get(section, {}).get(field)
        if not value:
            errors.append(f"{section}.{field}: required field is missing")
        elif isinstance(value, str) and value in PLACEHOLDER_VALUES:
            errors.append(f"{section}.{field}: contains placeholder value - please configure")
    
    # Check shelly.host (required)
    shelly_host = config.get('shelly', {}).get('host', '')
    if not shelly_host:
        errors.append("shelly.host: required field is missing")
    elif shelly_host in PLACEHOLDER_VALUES:
        errors.append("shelly.host: contains placeholder value - please configure")
    elif '://' in shelly_host:
        errors.append("shelly.host should be a hostname or IP address, not a URL (remove http:// or https://)")
    
    # Validate numeric ranges
    timeout = config.get('shelly', {}).get('timeout')
    if timeout is not None:
        if not isinstance(timeout, int) or timeout < 1 or timeout > 300:
            errors.append("shelly.timeout: must be an integer between 1 and 300")
    
    num_hours = config.get('scheduling', {}).get('num_cheapest_hours')
    if num_hours is not None:
        if not isinstance(num_hours, int) or num_hours < 1 or num_hours > 24:
            errors.append("scheduling.num_cheapest_hours: must be an integer between 1 and 24")
    
    if errors:
        raise ConfigValidationError(
            f"Configuration validation failed with {len(errors)} error(s)",
            details={"errors": errors}
        )

def get_config(require_home_id: bool = True) -> Dict[str, Any]:
    """
    Get validated configuration with defaults and environment overrides applied.
    
    Configuration is loaded in this order (later sources override earlier):
    1. config.json file
    2. Default values
    3. Environment variables (TIBBER_TOKEN, SHELLY_HOST, etc.)
    
    For type-safe access, use get_typed_config() instead.
    """
    config = load_config_dict()
    config = apply_defaults(config)
    config = apply_env_overrides(config)
    validate_config(config, require_home_id=require_home_id)
    return config


def get_typed_config(require_home_id: bool = True) -> AppConfig:
    """
    Get validated configuration as a typed AppConfig dataclass
    
    This provides type-safe access to configuration values:
        config = get_typed_config()
        token = config.tibber.token  # IDE autocomplete works!
        host = config.shelly.host
    """
    config_dict = get_config(require_home_id=require_home_id)
    return AppConfig.from_dict(config_dict) 