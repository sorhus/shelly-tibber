#!/usr/bin/env python3
"""
Unit tests for configuration module
"""

import unittest
import os
import json
import tempfile
from unittest.mock import patch

from src.config import (
    load_config,
    apply_defaults,
    validate_config,
    get_config,
    apply_env_overrides,
    PLACEHOLDER_VALUES,
)
from src.exceptions import ConfigFileNotFoundError, ConfigValidationError


class TestLoadConfig(unittest.TestCase):
    """Test configuration loading"""

    def test_load_config_file_not_found(self):
        """Test error when config file doesn't exist"""
        with patch('src.config.os.path.exists', return_value=False):
            with self.assertRaises(ConfigFileNotFoundError):
                load_config()

    def test_load_config_invalid_json(self):
        """Test error when config file has invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name
        
        try:
            with patch('src.config.os.path.exists', return_value=True):
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
            with patch('src.config.os.path.exists', return_value=True):
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
        self.assertIn('scheduling', result)
        self.assertEqual(result['tibber']['debug'], False)
        self.assertEqual(result['shelly']['timeout'], 10)
        self.assertEqual(result['shelly']['username'], '')
        self.assertEqual(result['shelly']['password'], '')
        self.assertEqual(result['scheduling']['num_cheapest_hours'], 10)

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

    def test_validate_missing_shelly_host(self):
        """Test validation fails without shelly.host"""
        config = {
            'tibber': {'token': 'test-token', 'home_id': 'home123'},
            'shelly': {}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('shelly.host', str(context.exception))

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
            with patch('src.config.os.path.exists', return_value=True):
                with patch('builtins.open', return_value=open(temp_path)):
                    config = get_config()
                    
                    # Check defaults were applied
                    self.assertEqual(config['tibber']['debug'], False)
                    self.assertEqual(config['shelly']['timeout'], 10)
                    
                    # Check original values preserved
                    self.assertEqual(config['tibber']['token'], 'test-token')
        finally:
            os.unlink(temp_path)


class TestEnvOverrides(unittest.TestCase):
    """Test environment variable overrides"""

    def test_env_override_string(self):
        """Test string environment variable override"""
        config = {
            'tibber': {'token': 'file-token'},
            'shelly': {}
        }
        
        with patch.dict(os.environ, {'TIBBER_TOKEN': 'env-token'}):
            result = apply_env_overrides(config)
            self.assertEqual(result['tibber']['token'], 'env-token')

    def test_env_override_integer(self):
        """Test integer environment variable override"""
        config = {
            'tibber': {},
            'shelly': {'timeout': 10}
        }
        
        with patch.dict(os.environ, {'SHELLY_TIMEOUT': '30'}):
            result = apply_env_overrides(config)
            self.assertEqual(result['shelly']['timeout'], 30)

    def test_env_override_boolean_true(self):
        """Test boolean environment variable override (true)"""
        config = {
            'tibber': {'debug': False},
            'shelly': {}
        }
        
        with patch.dict(os.environ, {'TIBBER_DEBUG': 'true'}):
            result = apply_env_overrides(config)
            self.assertTrue(result['tibber']['debug'])

    def test_env_override_boolean_false(self):
        """Test boolean environment variable override (false)"""
        config = {
            'tibber': {'debug': True},
            'shelly': {}
        }
        
        with patch.dict(os.environ, {'TIBBER_DEBUG': 'false'}):
            result = apply_env_overrides(config)
            self.assertFalse(result['tibber']['debug'])

    def test_env_override_creates_section(self):
        """Test that env override creates missing section"""
        config = {}
        
        with patch.dict(os.environ, {'SHELLY_HOST': '10.0.0.1'}):
            result = apply_env_overrides(config)
            self.assertEqual(result['shelly']['host'], '10.0.0.1')


class TestPlaceholderValidation(unittest.TestCase):
    """Test placeholder value detection"""

    def test_placeholder_token_rejected(self):
        """Test that placeholder token is rejected"""
        config = {
            'tibber': {'token': 'YOUR_TIBBER_API_TOKEN_HERE', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1'}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('placeholder', str(context.exception.details))

    def test_placeholder_host_rejected(self):
        """Test that placeholder host is rejected"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': 'YOUR_SHELLY_IP_HERE'}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('placeholder', str(context.exception.details))


class TestNumericValidation(unittest.TestCase):
    """Test numeric range validation"""

    def test_timeout_too_low(self):
        """Test timeout below minimum is rejected"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1', 'timeout': 0}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('timeout', str(context.exception.details))

    def test_timeout_too_high(self):
        """Test timeout above maximum is rejected"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1', 'timeout': 500}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('timeout', str(context.exception.details))

    def test_num_hours_too_low(self):
        """Test num_cheapest_hours below minimum is rejected"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1'},
            'scheduling': {'num_cheapest_hours': 0}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('num_cheapest_hours', str(context.exception.details))

    def test_num_hours_too_high(self):
        """Test num_cheapest_hours above maximum is rejected"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1'},
            'scheduling': {'num_cheapest_hours': 30}
        }
        
        with self.assertRaises(ConfigValidationError) as context:
            validate_config(config)
        
        self.assertIn('num_cheapest_hours', str(context.exception.details))

    def test_valid_numeric_values(self):
        """Test valid numeric values pass validation"""
        config = {
            'tibber': {'token': 'valid-token', 'home_id': 'home123'},
            'shelly': {'host': '192.168.1.1', 'timeout': 30},
            'scheduling': {'num_cheapest_hours': 10}
        }
        
        # Should not raise
        validate_config(config)


if __name__ == '__main__':
    unittest.main()
