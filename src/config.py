#!/usr/bin/env python3
"""
Configuration Management Module
Handles loading configuration from config.json file
"""

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json file
    """
    config_file = 'config.json'
    
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {config_file}")
        return config
    except (json.JSONDecodeError, IOError) as e:
        raise Exception(f"Failed to load config from {config_file}: {e}")

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
        raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

def get_config(require_home_id: bool = True) -> Dict[str, Any]:
    """
    Get validated configuration with defaults applied
    """
    config = load_config()
    config = apply_defaults(config)
    validate_config(config, require_home_id=require_home_id)
    return config 