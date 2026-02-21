#!/usr/bin/env python3
"""
Shelly Schedule Management Module
Handles creating, updating, and deleting schedules on Shelly devices
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.exceptions import (
    ShellyConnectionError,
    ShellyTimeoutError,
    ShellyRPCError,
    ScheduleCreationError,
    ScheduleDeletionError,
)
from src.http_client import ShellyClient
from src.retry import RetryConfig

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
    
    def __init__(
        self, 
        shelly_host: str, 
        timeout: int = 10, 
        debug: bool = False,
        dry_run: bool = False,
        retry_config: Optional[RetryConfig] = None
    ):
        self.shelly_host = shelly_host
        self.timeout = timeout
        self.debug = debug
        self.dry_run = dry_run
        self.client = ShellyClient(
            host=shelly_host,
            timeout=timeout,
            retry_config=retry_config,
            debug=debug,
        )
        self.logger = logging.getLogger(__name__)
        self._dry_run_schedule_counter = 0  # For generating fake schedule IDs in dry-run mode
    
    def debug_log(self, message: str):
        """Debug logging function"""
        if self.debug:
            self.logger.debug(f"[DEBUG] {message}")
        
    def _make_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an RPC request to the Shelly device via ShellyClient"""
        return self.client.rpc_call(method, params)
    
    def list_schedules(self) -> List[ScheduleJob]:
        """List all existing schedules"""
        self.logger.info("Fetching existing schedules...")
        
        if self.dry_run:
            self.logger.info("[DRY RUN] Would fetch schedules from device - returning empty list")
            return []
        
        result = self._make_request("Schedule.List")
        jobs = result.get("jobs", [])
        
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
    
    def create_schedule(self, timespec: str, calls: List[Dict[str, Any]], enable: bool = True) -> int:
        """Create a new schedule"""
        self.logger.info(f"Creating schedule: {timespec}")
        
        if self.dry_run:
            self._dry_run_schedule_counter += 1
            fake_id = self._dry_run_schedule_counter
            action = "ON" if calls and calls[0].get("params", {}).get("on") else "OFF"
            self.logger.info(f"[DRY RUN] Would create schedule (fake ID: {fake_id}): {timespec} -> {action}")
            return fake_id
        
        try:
            params = {
                "enable": enable,
                "timespec": timespec,
                "calls": calls
            }
            
            result = self._make_request("Schedule.Create", params)
            schedule_id = result.get("id")
            
            self.logger.info(f"Created schedule with ID: {schedule_id}")
            return schedule_id
            
        except (ShellyConnectionError, ShellyTimeoutError, ShellyRPCError) as e:
            raise ScheduleCreationError(
                f"Failed to create schedule: {str(e)}",
                details={"timespec": timespec, "original_error": str(e)}
            )
    
    def update_schedule(self, schedule_id: int, **kwargs) -> int:
        """Update an existing schedule"""
        self.logger.info(f"Updating schedule {schedule_id}")

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would update schedule {schedule_id}")
            return 0

        params = {"id": schedule_id}
        params.update(kwargs)
        
        result = self._make_request("Schedule.Update", params)
        revision = result.get("rev")
        
        self.logger.info(f"Updated schedule {schedule_id}, revision: {revision}")
        return revision
    
    def delete_schedule(self, schedule_id: int) -> int:
        """Delete a specific schedule"""
        self.logger.info(f"Deleting schedule {schedule_id}")
        
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would delete schedule {schedule_id}")
            return 0
        
        try:
            params = {"id": schedule_id}
            result = self._make_request("Schedule.Delete", params)
            revision = result.get("rev")
            
            self.logger.info(f"Deleted schedule {schedule_id}, revision: {revision}")
            return revision
            
        except (ShellyConnectionError, ShellyTimeoutError, ShellyRPCError) as e:
            raise ScheduleDeletionError(
                f"Failed to delete schedule {schedule_id}: {str(e)}",
                details={"schedule_id": schedule_id, "original_error": str(e)}
            )
    
    def delete_all_schedules(self) -> int:
        """Delete all schedules"""
        self.logger.info("Deleting all schedules")
        
        if self.dry_run:
            self.logger.info("[DRY RUN] Would delete all schedules")
            return 0
        
        try:
            result = self._make_request("Schedule.DeleteAll")
            revision = result.get("rev")
            
            self.logger.info(f"Deleted all schedules, revision: {revision}")
            return revision
            
        except (ShellyConnectionError, ShellyTimeoutError, ShellyRPCError) as e:
            raise ScheduleDeletionError(
                f"Failed to delete all schedules: {str(e)}",
                details={"original_error": str(e)}
            )
    
    def delete_schedules_for_weekdays(self, weekdays: List[int]) -> int:
        """Delete schedules that match specific weekdays
        
        Args:
            weekdays: List of weekday numbers (0=Sunday, 1=Monday, ..., 6=Saturday)
        
        Returns:
            Number of schedules deleted
        """
        self.logger.info(f"Deleting schedules for weekdays: {weekdays}")
        
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
        if self.dry_run:
            self.logger.info("[DRY RUN] Would test connection to Shelly device - skipping")
            return True
        
        try:
            # Try to get device info
            result = self._make_request("Shelly.GetDeviceInfo")
            device_info = result
            
            self.logger.info(f"Connected to Shelly device: {device_info.get('model', 'Unknown')}")
            self.logger.info(f"Firmware version: {device_info.get('version', 'Unknown')}")
            
            return True
            
        except (ShellyConnectionError, ShellyTimeoutError, ShellyRPCError) as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False