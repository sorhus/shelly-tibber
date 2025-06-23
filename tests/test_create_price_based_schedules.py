#!/usr/bin/env python3
"""
Unit tests for create_price_based_schedules method
"""

import unittest
from unittest.mock import Mock, patch, call
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from shelly_schedule import ShellyScheduleManager


class TestCreatePriceBasedSchedules(unittest.TestCase):
    """Test cases for create_price_based_schedules method"""

    def setUp(self):
        """Set up test fixtures"""
        self.schedule_manager = ShellyScheduleManager("192.168.1.100")
        self.schedule_manager.logger = Mock()

    def test_empty_price_points(self):
        """Test with empty price points list"""
        price_points = []
        
        schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        self.assertEqual(schedule_ids, [])
        self.assertEqual(consecutive_blocks, [])

    def test_single_price_point(self):
        """Test with a single price point"""
        price_points = [
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5}
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2]  # ON schedule ID, OFF schedule ID
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should create 2 schedules (ON and OFF) for 1 block
        self.assertEqual(len(schedule_ids), 2)
        self.assertEqual(schedule_ids, [1, 2])
        self.assertEqual(len(consecutive_blocks), 1)
        
        # Check that create_switch_schedule was called correctly
        expected_calls = [
            call(hour=10, minute=0, switch_id=0, turn_on=True),  # ON at 10:00
            call(hour=11, minute=0, switch_id=0, turn_on=False)  # OFF at 11:00
        ]
        self.assertEqual(mock_create.call_args_list, expected_calls)

    def test_consecutive_hours(self):
        """Test with consecutive hours (should create one block)"""
        price_points = [
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5},
            {'startsAt': '2024-01-15T11:00:00Z', 'total': 0.3},
            {'startsAt': '2024-01-15T12:00:00Z', 'total': 0.4}
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 4]  # ON at 10:00, OFF at 13:00
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should create 2 schedules (ON and OFF) for 1 consecutive block
        self.assertEqual(len(schedule_ids), 2)
        self.assertEqual(schedule_ids, [1, 4])
        self.assertEqual(len(consecutive_blocks), 1)
        
        # Check that create_switch_schedule was called correctly
        expected_calls = [
            call(hour=10, minute=0, switch_id=0, turn_on=True),   # ON at 10:00
            call(hour=13, minute=0, switch_id=0, turn_on=False)   # OFF at 13:00 (3 hours later)
        ]
        self.assertEqual(mock_create.call_args_list, expected_calls)

    def test_non_consecutive_hours(self):
        """Test with non-consecutive hours (should create multiple blocks)"""
        price_points = [
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5},
            {'startsAt': '2024-01-15T14:00:00Z', 'total': 0.3},  # Gap of 2 hours
            {'startsAt': '2024-01-15T22:00:00Z', 'total': 0.4}   # Gap of 7 hours
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2, 3, 4, 5, 6]  # ON/OFF for each block
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should create 6 schedules (ON and OFF for each of 3 blocks)
        self.assertEqual(len(schedule_ids), 6)
        self.assertEqual(schedule_ids, [1, 2, 3, 4, 5, 6])
        self.assertEqual(len(consecutive_blocks), 3)
        
        # Check that create_switch_schedule was called correctly
        expected_calls = [
            call(hour=10, minute=0, switch_id=0, turn_on=True),   # ON at 10:00 (block 1)
            call(hour=11, minute=0, switch_id=0, turn_on=False),  # OFF at 11:00 (block 1)
            call(hour=14, minute=0, switch_id=0, turn_on=True),   # ON at 14:00 (block 2)
            call(hour=15, minute=0, switch_id=0, turn_on=False),  # OFF at 15:00 (block 2)
            call(hour=22, minute=0, switch_id=0, turn_on=True),   # ON at 22:00 (block 3)
            call(hour=23, minute=0, switch_id=0, turn_on=False)   # OFF at 23:00 (block 3)
        ]
        self.assertEqual(mock_create.call_args_list, expected_calls)

    def test_mixed_consecutive_and_non_consecutive(self):
        """Test with mixed consecutive and non-consecutive hours"""
        price_points = [
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5},
            {'startsAt': '2024-01-15T11:00:00Z', 'total': 0.3},  # Consecutive
            {'startsAt': '2024-01-15T14:00:00Z', 'total': 0.4},  # Gap of 2 hours
            {'startsAt': '2024-01-15T15:00:00Z', 'total': 0.2},  # Consecutive
            {'startsAt': '2024-01-15T16:00:00Z', 'total': 0.1}   # Consecutive
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2, 3, 4]  # ON/OFF for each block
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should create 4 schedules (ON and OFF for each of 2 blocks)
        self.assertEqual(len(schedule_ids), 4)
        self.assertEqual(schedule_ids, [1, 2, 3, 4])
        self.assertEqual(len(consecutive_blocks), 2)
        
        # Check that create_switch_schedule was called correctly
        expected_calls = [
            call(hour=10, minute=0, switch_id=0, turn_on=True),   # ON at 10:00 (block 1: 10-12)
            call(hour=12, minute=0, switch_id=0, turn_on=False),  # OFF at 12:00 (block 1)
            call(hour=14, minute=0, switch_id=0, turn_on=True),   # ON at 14:00 (block 2: 14-17)
            call(hour=17, minute=0, switch_id=0, turn_on=False),  # OFF at 17:00 (block 2)
        ]
        self.assertEqual(mock_create.call_args_list, expected_calls)

    def test_unsorted_price_points(self):
        """Test that price points are sorted by start time"""
        price_points = [
            {'startsAt': '2024-01-15T11:00:00Z', 'total': 0.3},
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5},  # Earlier time
            {'startsAt': '2024-01-15T12:00:00Z', 'total': 0.4}
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2]  # ON at 10:00, OFF at 13:00
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should create 2 schedules for 1 consecutive block (10-13)
        self.assertEqual(len(schedule_ids), 2)
        self.assertEqual(schedule_ids, [1, 2])
        self.assertEqual(len(consecutive_blocks), 1)
        
        # Check that create_switch_schedule was called correctly (sorted by time)
        expected_calls = [
            call(hour=10, minute=0, switch_id=0, turn_on=True),   # ON at 10:00 (earliest)
            call(hour=13, minute=0, switch_id=0, turn_on=False)   # OFF at 13:00 (3 hours later)
        ]
        self.assertEqual(mock_create.call_args_list, expected_calls)

    def test_consecutive_blocks_structure(self):
        """Test that consecutive_blocks contains correct datetime tuples"""
        price_points = [
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5},
            {'startsAt': '2024-01-15T11:00:00Z', 'total': 0.3},
            {'startsAt': '2024-01-15T14:00:00Z', 'total': 0.4}
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2, 3, 4]  # ON/OFF for each block
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should have 2 blocks
        self.assertEqual(len(consecutive_blocks), 2)
        
        # Check first block (10:00-12:00)
        block1_start, block1_end = consecutive_blocks[0]
        self.assertEqual(block1_start.hour, 10)
        self.assertEqual(block1_start.minute, 0)
        self.assertEqual(block1_end.hour, 12)
        self.assertEqual(block1_end.minute, 0)
        
        # Check second block (14:00-15:00)
        block2_start, block2_end = consecutive_blocks[1]
        self.assertEqual(block2_start.hour, 14)
        self.assertEqual(block2_start.minute, 0)
        self.assertEqual(block2_end.hour, 15)
        self.assertEqual(block2_end.minute, 0)

    def test_different_switch_id(self):
        """Test with a different switch_id"""
        price_points = [
            {'startsAt': '2024-01-15T10:00:00Z', 'total': 0.5}
        ]
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            mock_create.side_effect = [1, 2]
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(
                price_points, switch_id=1
            )
        
        # Check that create_switch_schedule was called with correct switch_id
        expected_calls = [
            call(hour=10, minute=0, switch_id=1, turn_on=True),   # ON at 10:00, switch_id=1
            call(hour=11, minute=0, switch_id=1, turn_on=False)   # OFF at 11:00, switch_id=1
        ]
        self.assertEqual(mock_create.call_args_list, expected_calls)

    def test_processes_all_price_points(self):
        """Test that the method processes all price points it receives (not limited to 10)"""
        # Create 12 price points (more than the "10 cheapest hours" mentioned in old comment)
        price_points = []
        for i in range(12):
            hour = i  # 0:00, 1:00, ..., 11:00 (valid hours 0-23)
            price_points.append({
                'startsAt': f'2024-01-15T{hour:02d}:00:00Z',
                'total': 0.5 - (i * 0.01)  # Decreasing prices
            })
        
        with patch.object(self.schedule_manager, 'create_switch_schedule') as mock_create:
            # Mock 2 schedule IDs (ON and OFF for the block)
            mock_create.side_effect = [1, 2]
            
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(price_points)
        
        # Should process all 12 price points, creating 2 schedules (ON at first, OFF at last)
        self.assertEqual(len(schedule_ids), 2)
        self.assertEqual(len(consecutive_blocks), 1)  # All consecutive hours = 1 block
        
        # Verify that create_switch_schedule was called 2 times
        self.assertEqual(mock_create.call_count, 2)
        
        # Check first and last calls
        first_call = mock_create.call_args_list[0]
        last_call = mock_create.call_args_list[-1]
        
        # First call should be ON at 00:00
        self.assertEqual(first_call, call(hour=0, minute=0, switch_id=0, turn_on=True))
        
        # Last call should be OFF at 12:00
        self.assertEqual(last_call, call(hour=12, minute=0, switch_id=0, turn_on=False))


if __name__ == '__main__':
    unittest.main() 