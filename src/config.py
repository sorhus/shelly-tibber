#!/usr/bin/env python3
"""
Configuration Management Module
Handles loading configuration from config.json file
"""

import os
import json
import logging
from typing import Dict, Any, Union, overload, Literal

from models import AppConfig

from exceptions import (
    ConfigFileNotFoundError,
    ConfigValidationError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)


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
    Validate that required configuration values are present
    """
    required_fields = [
        ('tibber', 'token'),
    ]
    if require_home_id:
        required_fields.append(('tibber', 'home_id'))
    
    missing_fields = []
    for section, field in required_fields:
        if not config.get(section, {}).get(field):
            missing_fields.append(f"{section}.{field}")
    
    if missing_fields:
        raise ConfigValidationError(
            f"Missing required configuration fields: {', '.join(missing_fields)}",
            details={"missing_fields": missing_fields}
        )

def get_config(require_home_id: bool = True) -> Dict[str, Any]:
    """
    Get validated configuration with defaults applied (as dictionary)
    
    For type-safe access, use get_typed_config() instead.
    """
    config = load_config_dict()
    config = apply_defaults(config)
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