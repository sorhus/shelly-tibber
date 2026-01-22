#!/usr/bin/env python3
"""
Unit tests for configuration module
"""

import unittest
import sys
import os
import json
import tempfile
from unittest.mock import patch

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import load_config, apply_defaults, validate_config, get_config
from exceptions import ConfigFileNotFoundError, ConfigValidationError


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading"""

    def test_load_config_file_not_found(self):
        """Test error when config file doesn't exist"""
        with patch('config.os.path.exists', return_value=False):
            with self.assertRaises(ConfigFileNotFoundError):
                load_config()

    def test_load_config_invalid_json(self):
        """Test error when config file has invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            with patch('config.os.path.exists', return_value=True):
                with patch('builtins.open', return_value=open(temp_path)):
                    with self.assertRaises(Exception):
                        load_config()
        finally:
            os.unlink(temp_path)

    def test_load_config_success(self):
        """Test successful config loading"""
        test_config = {
            "tibber": {"token": "test", "home_id": "home123"},
            "shelly": {"host": "192.168.1.1"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_path = f.name
        
        try:
            # Patch to use our temp file
            with patch('config.os.path.exists', return_value=True):
                with patch('builtins.open', return_value=open(temp_path)):
                    config = load_config()
                    self.assertEqual(config["tibber"]["token"], "test")
        finally:
            os.unlink(temp_path)


class TestApplyDefaults(unittest.TestCase):
    """Test default value application"""

    def test_apply_defaults_empty_config(self):
        """Test defaults applied to empty config"""
        config = {}
        result = apply_defaults(config)
        
        self.assertIn('tibber', result)
        self.assertIn('shelly', result)
        self.assertEqual(result['tibber']['debug'], False)
        self.assertEqual(result['shelly']['timeout'], 10)
        self.assertEqual(result['shelly']['username'], '')
        self.assertEqual(result['shelly']['password'], '')

    def test_apply_defaults_preserves_existing(self):
        """Test defaults don't overwrite existing values"""
        config = {
            'tibber': {'debug': True},
            'shelly': {'timeout': 30, 'username': 'admin'}
        }
        result = apply_defaults(config)
        
        self.assertEqual(result['tibber']['debug'], True)
        self.assertEqual(result['shelly']['timeout'], 30)
        self.assertEqual(result['shelly']['username'], 'admin')
        # But missing values get defaults
        self.assertEqual(result['shelly']['password'], '')

    def test_apply_defaults_handles_none_values(self):
        """Test None values are replaced with defaults"""
        config = {
            'tibber': {'debug': None},
            'shelly': {'timeout': None}
        }
        result = apply_defaults(config)
        
        self.assertEqual(result['tibber']['debug'], False)
        self.assertEqual(result['shelly']['timeout'], 10)


class TestValidateConfig(unittest.TestCase):
    """Test configuration validation"""

    def test_validate_missing_token(self):
        """Test validation fails without token"""
        config = {
            'tibber': {'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1'}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('tibber.token', str(context.exception))

    def test_validate_missing_home_id(self):
        """Test validation fails without home_id when required"""
        config = {
            'tibber': {'token': 'test-token'},
            'shelly': {'host': '192.168.1.1'}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config, require_home_id=True)
        
        self.assertIn('tibber.home_id', str(context.exception))

    def test_validate_home_id_not_required(self):
        """Test validation passes without home_id when not required"""
        config = {
            'tibber': {'token': 'test-token'},
            'shelly': {'host': '192.168.1.1'}
        }
        
        # Should not raise
        validate_config(config, require_home_id=False)

    def test_validate_empty_token(self):
        """Test validation fails with empty token"""
        config = {
            'tibber': {'token': '', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1'}
        }
        
        with self.assertRaises(ConfigValidationError):
            validate_config(config)

    def test_validate_success(self):
        """Test validation passes with valid config"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1'}
        }
        
        # Should not raise
        validate_config(config)


class TestGetConfig(unittest.TestCase):
    """Test the combined get_config function"""

    def test_get_config_applies_defaults_and_validates(self):
        """Test get_config applies defaults and validates"""
        test_config = {
            "tibber": {"token": "test-token", "home_id": "home123"},
            "shelly": {"host": "192.168.1.1"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            temp_path = f.name
        
        try:
            with patch('config.os.path.exists', return_value=True):
                with patch('builtins.open', return_value=open(temp_path)):
                    config = get_config()
                    
                    # Check defaults were applied
                    self.assertEqual(config['tibber']['debug'], False)
                    self.assertEqual(config['shelly']['timeout'], 10)
                    
                    # Check original values preserved
                    self.assertEqual(config['tibber']['token'], 'test-token')
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
