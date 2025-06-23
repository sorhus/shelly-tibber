#!/usr/bin/env python3
"""
Shelly Schedule Management Module
Handles creating, updating, and deleting schedules on Shelly devices
"""

import requests
import logging
import os
import json
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ScheduleJob:
    """Represents a Shelly schedule job"""
    id: Optional[int] = None
    enable: bool = True
    timespec: str = ""
    calls: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

class ShellyScheduleManager:
    """Manages schedules on Shelly devices"""
    
    def __init__(self, shelly_host: str, timeout: int = 10):
        self.shelly_host = shelly_host
        self.timeout = timeout
        self.base_url = f"http://{shelly_host}/rpc"
        self.logger = logging.getLogger(__name__)
        
    def _make_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an RPC request to the Shelly device and log the call to output/"""
        payload = {
            "id": 1,
            "method": method
        }
        if params:
            payload["params"] = params

        # Helper function to safely serialize objects for JSON logging
        def safe_json_serialize(obj):
            """Safely serialize objects for JSON logging, handling Mock objects"""
            if obj is None:
                return None
            if hasattr(obj, '__class__') and 'Mock' in obj.__class__.__name__:
                return f"<Mock object: {obj.__class__.__name__}>"
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, (list, tuple)):
                return [safe_json_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {str(k): safe_json_serialize(v) for k, v in obj.items()}
            try:
                # Try to serialize normally
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                # If serialization fails, convert to string
                return str(obj)

        # Prepare log data with safe serialization
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "params": safe_json_serialize(params),
            "request": safe_json_serialize(payload)
        }
        
        # Create daily subdirectory for logs
        today = datetime.now().strftime('%Y-%m-%d')
        log_dir = os.path.join("output", today)
        os.makedirs(log_dir, exist_ok=True)
        
        log_filename = os.path.join(
            log_dir,
            f"shelly_call_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}.json"
        )
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=self.timeout
            )
            log_data["http_status"] = response.status_code
            log_data["response_text"] = response.text
            try:
                result = response.json()
                log_data["response_json"] = safe_json_serialize(result)
            except Exception:
                result = None
                log_data["response_json"] = None
            # Check for RPC errors
            if result and "error" in result:
                log_data["rpc_error"] = safe_json_serialize(result["error"])
                with open(log_filename, "w") as f:
                    json.dump(log_data, f, indent=2)
                raise Exception(f"RPC Error: {result['error']}")
            with open(log_filename, "w") as f:
                json.dump(log_data, f, indent=2)
            return result.get("params", result) if result else None
        except requests.exceptions.RequestException as e:
            log_data["exception"] = str(e)
            with open(log_filename, "w") as f:
                json.dump(log_data, f, indent=2)
            raise Exception(f"Request failed: {str(e)}")
        except Exception as e:
            log_data["exception"] = str(e)
            with open(log_filename, "w") as f:
                json.dump(log_data, f, indent=2)
            raise Exception(f"Unexpected error: {str(e)}")
    
    def list_schedules(self) -> List[ScheduleJob]:
        """List all existing schedules"""
        self.logger.info("Fetching existing schedules...")
        
        try:
            result = self._make_request("Schedule.List")
            jobs = result.get("result", {}).get("jobs", [])
            
            schedule_jobs = []
            for job in jobs:
                schedule_jobs.append(ScheduleJob(
                    id=job.get("id"),
                    enable=job.get("enable", True),
                    timespec=job.get("timespec", ""),
                    calls=job.get("calls", [])
                ))
            
            self.logger.info(f"Found {len(schedule_jobs)} existing schedules")
            return schedule_jobs
            
        except Exception as e:
            self.logger.error(f"Failed to list schedules: {str(e)}")
            raise
    
    def create_schedule(self, timespec: str, calls: List[Dict[str, Any]], enable: bool = True) -> int:
        """Create a new schedule"""
        self.logger.info(f"Creating schedule: {timespec}")
        
        try:
            params = {
                "enable": enable,
                "timespec": timespec,
                "calls": calls
            }
            
            result = self._make_request("Schedule.Create", params)
            schedule_id = result.get("result", {}).get("id")
            
            self.logger.info(f"Created schedule with ID: {schedule_id}")
            return schedule_id
            
        except Exception as e:
            self.logger.error(f"Failed to create schedule: {str(e)}")
            raise
    
    def update_schedule(self, schedule_id: int, **kwargs) -> int:
        """Update an existing schedule"""
        self.logger.info(f"Updating schedule {schedule_id}")
        
        try:
            params = {"id": schedule_id}
            params.update(kwargs)
            
            result = self._make_request("Schedule.Update", params)
            revision = result.get("rev")
            
            self.logger.info(f"Updated schedule {schedule_id}, revision: {revision}")
            return revision
            
        except Exception as e:
            self.logger.error(f"Failed to update schedule {schedule_id}: {str(e)}")
            raise
    
    def delete_schedule(self, schedule_id: int) -> int:
        """Delete a specific schedule"""
        self.logger.info(f"Deleting schedule {schedule_id}")
        
        try:
            params = {"id": schedule_id}
            result = self._make_request("Schedule.Delete", params)
            revision = result.get("rev")
            
            self.logger.info(f"Deleted schedule {schedule_id}, revision: {revision}")
            return revision
            
        except Exception as e:
            self.logger.error(f"Failed to delete schedule {schedule_id}: {str(e)}")
            raise
    
    def delete_all_schedules(self) -> int:
        """Delete all schedules"""
        self.logger.info("Deleting all schedules")
        
        try:
            result = self._make_request("Schedule.DeleteAll")
            revision = result.get("rev")
            
            self.logger.info(f"Deleted all schedules, revision: {revision}")
            return revision
            
        except Exception as e:
            self.logger.error(f"Failed to delete all schedules: {str(e)}")
            raise
    
    def create_switch_schedule(self, hour: int, minute: int = 0, switch_id: int = 0, 
                              turn_on: bool = True, days: str = "*") -> int:
        """Create a simple switch schedule for a specific time"""
        timespec = f"0 {minute} {hour} * * {days}"
        
        calls = [{
            "method": "Switch.Set",
            "params": {
                "id": switch_id,
                "on": turn_on
            }
        }]
        
        return self.create_schedule(timespec, calls)
    
    def create_price_based_schedules(self, price_points: List[Dict[str, Any]], 
                                   switch_id: int = 0) -> tuple[List[int], List[tuple]]:
        """
        Create schedules based on price points.
        Identifies consecutive hours and creates continuous blocks for all provided price points.
        The number of price points should be limited by the calling code (e.g., PriceAnalyzer).
        
        Args:
            price_points: List of price points with 'startsAt' timestamps
            switch_id: Switch ID to control
            
        Returns:
            Tuple of (schedule_ids, consecutive_blocks)
        """
        self.logger.info(f"Creating price-based schedules for {len(price_points)} price points")
        
        schedule_ids = []
        
        # Sort price points by start time
        sorted_price_points = sorted(price_points, key=lambda x: x['startsAt'])
        
        if not sorted_price_points:
            return schedule_ids, []
        
        # Convert to datetime objects
        start_times = []
        for price_point in sorted_price_points:
            start_time = datetime.fromisoformat(price_point['startsAt'].replace('Z', '+00:00'))
            start_times.append(start_time)
        
        # Find consecutive blocks
        consecutive_blocks = []
        current_block_start = start_times[0]
        current_block_end = start_times[0] + timedelta(hours=1)
        
        for i in range(1, len(start_times)):
            current_time = start_times[i]
            expected_time = current_block_end
            
            if current_time == expected_time:
                # Consecutive hour, extend the block
                current_block_end = current_time + timedelta(hours=1)
            else:
                # Non-consecutive, save current block and start new one
                consecutive_blocks.append((current_block_start, current_block_end))
                current_block_start = current_time
                current_block_end = current_time + timedelta(hours=1)
        
        # Don't forget the last block
        consecutive_blocks.append((current_block_start, current_block_end))
        
        self.logger.info(f"Found {len(consecutive_blocks)} consecutive blocks")
        
        # Create schedules for each consecutive block
        for i, (block_start, block_end) in enumerate(consecutive_blocks):
            self.logger.info(f"Creating block {i+1}: {block_start.strftime('%H:%M')} - {block_end.strftime('%H:%M')}")
            
            # Create ON schedule at the start of this block
            on_schedule_id = self.create_switch_schedule(
                hour=block_start.hour,
                minute=block_start.minute,
                switch_id=switch_id,
                turn_on=True
            )
            schedule_ids.append(on_schedule_id)
            
            self.logger.info(f"Created ON schedule {on_schedule_id} for {block_start.strftime('%H:%M')}")
            
            # Create OFF schedule at the end of this block
            off_schedule_id = self.create_switch_schedule(
                hour=block_end.hour,
                minute=block_end.minute,
                switch_id=switch_id,
                turn_on=False
            )
            schedule_ids.append(off_schedule_id)
            
            self.logger.info(f"Created OFF schedule {off_schedule_id} for {block_end.strftime('%H:%M')}")
        
        total_hours = sum((end - start).total_seconds() / 3600 for start, end in consecutive_blocks)
        self.logger.info(f"Created {len(schedule_ids)} schedules total ({len(consecutive_blocks)} blocks, {total_hours:.1f} hours)")
        return schedule_ids, consecutive_blocks
    
    def test_connection(self) -> bool:
        """Test connection to Shelly device"""
        try:
            # Try to get device info
            result = self._make_request("Shelly.GetDeviceInfo")
            device_info = result
            
            self.logger.info(f"Connected to Shelly device: {device_info.get('model', 'Unknown')}")
            self.logger.info(f"Firmware version: {device_info.get('version', 'Unknown')}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False 