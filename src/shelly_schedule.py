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
from datetime import datetime, timedelta, timezone

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
    
    def __init__(self, shelly_host: str, timeout: int = 10, debug: bool = False):
        self.shelly_host = shelly_host
        self.timeout = timeout
        self.debug = debug
        self.base_url = f"http://{shelly_host}/rpc"
        self.logger = logging.getLogger(__name__)
    
    def debug_log(self, message: str):
        """Debug logging function"""
        if self.debug:
            self.logger.debug(f"[DEBUG] {message}")
        
    def _make_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an RPC request to the Shelly device and log the call to output/ if debug mode is enabled"""
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

        # Only prepare log data if debug mode is enabled
        log_data = None
        log_filename = None
        
        if self.debug:
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
            
            # Only log response data if debug mode is enabled
            if self.debug and log_data:
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
                
                # Write successful response to log file
                with open(log_filename, "w") as f:
                    json.dump(log_data, f, indent=2)
            else:
                # Parse response without logging
                try:
                    result = response.json()
                except Exception:
                    result = None
                
                # Check for RPC errors even without logging
                if result and "error" in result:
                    raise Exception(f"RPC Error: {result['error']}")
            
            return result.get("params", result) if result else None
            
        except requests.exceptions.RequestException as e:
            # Log exception if debug mode is enabled
            if self.debug and log_data and log_filename:
                log_data["exception"] = str(e)
                with open(log_filename, "w") as f:
                    json.dump(log_data, f, indent=2)
            raise Exception(f"Request failed: {str(e)}")
        except Exception as e:
            # Log exception if debug mode is enabled
            if self.debug and log_data and log_filename:
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
    
    def delete_schedules_for_weekdays(self, weekdays: List[int]) -> int:
        """Delete schedules that match specific weekdays
        
        Args:
            weekdays: List of weekday numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
        
        Returns:
            Number of schedules deleted
        """
        self.logger.info(f"Deleting schedules for weekdays: {weekdays}")
        
        try:
            # Get all existing schedules
            schedules = self.list_schedules()
            
            deleted_count = 0
            for schedule in schedules:
                # Parse the timespec to check if it matches our weekdays
                # Timespec format: "0 minute hour * * weekday"
                timespec_parts = schedule.timespec.split()
                if len(timespec_parts) >= 6:
                    schedule_weekdays = timespec_parts[5]
                    
                    # Check if any of the target weekdays match this schedule
                    # Handle both single weekday (e.g., "1") and comma-separated (e.g., "1,2,3")
                    schedule_weekday_list = schedule_weekdays.split(',')
                    
                    for target_weekday in weekdays:
                        if str(target_weekday) in schedule_weekday_list:
                            self.logger.info(f"Deleting schedule {schedule.id} (weekday {schedule_weekdays})")
                            self.delete_schedule(schedule.id)
                            deleted_count += 1
                            break
            
            self.logger.info(f"Deleted {deleted_count} schedules for weekdays {weekdays}")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to delete schedules for weekdays {weekdays}: {str(e)}")
            raise
    
    def create_switch_schedule(self, hour: int, minute: int = 0, switch_id: int = 0, 
                              turn_on: bool = True, days: str = "*", weekdays: Optional[List[int]] = None) -> int:
        """Create a simple switch schedule for a specific time
        
        Args:
            hour: Hour of day (0-23)
            minute: Minute of hour (0-59)
            switch_id: Switch ID to control
            turn_on: Whether to turn on (True) or off (False)
            days: Day of month specification (* for all, or specific day)
            weekdays: Optional list of weekday numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
                     If provided, overrides the 'days' parameter
        """
        # If weekdays are specified, use them instead of the days parameter
        if weekdays is not None:
            # Convert weekdays list to comma-separated string for cron
            weekday_str = ",".join(str(d) for d in weekdays)
            timespec = f"0 {minute} {hour} * * {weekday_str}"
        else:
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
                                   switch_id: int = 0, weekdays: Optional[List[int]] = None) -> tuple[List[int], List[tuple]]:
        """
        Create schedules based on price points.
        Identifies consecutive hours and creates continuous blocks for all provided price points.
        The number of price points should be limited by the calling code (e.g., PriceAnalyzer).
        
        Args:
            price_points: List of price points with 'startsAt' timestamps
            switch_id: Switch ID to control
            weekdays: Optional list of weekday numbers (0=Sunday, 1=Monday, ..., 6=Saturday) for the schedule to run on
            
        Returns:
            Tuple of (schedule_ids, consecutive_blocks)
        """
        self.logger.info(f"Creating price-based schedules for {len(price_points)} price points")
        if weekdays:
            self.logger.info(f"Schedules will run on weekdays: {weekdays}")
        
        schedule_ids = []
        
        # Convert to datetime objects and sort by absolute time (UTC)
        time_tuples = []
        for price_point in price_points:
            start_time = datetime.fromisoformat(price_point['startsAt'].replace('Z', '+00:00'))
            time_tuples.append((start_time, price_point))
        
        # Sort by UTC time to handle DST transitions correctly
        time_tuples.sort(key=lambda x: x[0].astimezone(timezone.utc))
        
        if not time_tuples:
            return schedule_ids, []
        
        start_times = [t[0] for t in time_tuples]
        
        # Debug: Log sorted times to verify DST handling
        self.debug_log("Sorted price points by UTC time:")
        for i, st in enumerate(start_times):
            utc_time = st.astimezone(timezone.utc)
            self.debug_log(f"  {i+1}. Local: {st.isoformat()} | UTC: {utc_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Find consecutive blocks (check if times are exactly 1 hour apart in absolute time)
        consecutive_blocks = []
        current_block_start = start_times[0]
        current_block_end = start_times[0] + timedelta(hours=1)
        
        for i in range(1, len(start_times)):
            current_time = start_times[i]
            expected_time = current_block_end
            
            # Compare absolute time difference (handles DST transitions)
            time_diff = abs((current_time - expected_time).total_seconds())
            
            self.debug_log(f"Checking hour {i+1}: current={current_time.strftime('%H:%M%z')} expected={expected_time.strftime('%H:%M%z')} diff={time_diff}s")
            
            if time_diff < 60:  # Less than 1 minute difference means consecutive
                # Consecutive hour, extend the block
                self.debug_log(f"  → Consecutive! Extending block to {(current_time + timedelta(hours=1)).strftime('%H:%M%z')}")
                current_block_end = current_time + timedelta(hours=1)
            else:
                # Non-consecutive, save current block and start new one
                self.debug_log(f"  → Non-consecutive! Closing block {current_block_start.strftime('%H:%M%z')}-{current_block_end.strftime('%H:%M%z')}")
                consecutive_blocks.append((current_block_start, current_block_end))
                current_block_start = current_time
                current_block_end = current_time + timedelta(hours=1)
                self.debug_log(f"  → Starting new block at {current_block_start.strftime('%H:%M%z')}")
        
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
                turn_on=True,
                weekdays=weekdays
            )
            schedule_ids.append(on_schedule_id)
            
            self.logger.info(f"Created ON schedule {on_schedule_id} for {block_start.strftime('%H:%M')}")
            
            # Create OFF schedule at the end of this block
            # If block_end is on a different day than block_start, calculate the correct weekday for OFF
            off_weekdays = weekdays
            if weekdays and block_start.date() != block_end.date():
                # OFF time crosses into next day, use next day's weekday
                python_weekday = block_end.weekday()
                cron_weekday = (python_weekday + 1) % 7
                off_weekdays = [cron_weekday]
                self.logger.info(f"OFF time crosses midnight - using weekday {cron_weekday} ({block_end.strftime('%A')}) instead of {weekdays}")
            
            off_schedule_id = self.create_switch_schedule(
                hour=block_end.hour,
                minute=block_end.minute,
                switch_id=switch_id,
                turn_on=False,
                weekdays=off_weekdays
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