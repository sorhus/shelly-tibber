#!/usr/bin/env python3
"""
Cheapest Hours Scheduler
Main orchestrator for scheduling electricity usage during cheapest hours
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from src.price_analysis import PriceAnalyzer
from src.file_io import FileManager
from src.shelly_schedule import ShellyScheduleManager
from src.config import get_config
from src.retry import RetryConfig
from src.health_check import StatusManager, RunStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CheapestHoursScheduler:
    """Main orchestrator for scheduling cheapest hours"""

    def __init__(self, config: Dict[str, Any], dry_run: bool = False, status_manager: StatusManager = None):
        self.config = config
        self.dry_run = dry_run
        self.status_manager = status_manager or StatusManager()

        # Get retry configuration from config or use defaults
        retry_dict = config.get('retry', {})
        retry_config = RetryConfig.from_dict(retry_dict) if retry_dict else RetryConfig()

        self.price_analyzer = PriceAnalyzer(config, retry_config=retry_config)
        self.file_manager = FileManager()
        self.schedule_manager = ShellyScheduleManager(
            shelly_host=config['shelly']['host'],
            timeout=config['shelly']['timeout'],
            debug=config['tibber']['debug'],
            dry_run=dry_run,
            retry_config=retry_config
        )

        if dry_run:
            logger.info("=" * 60)
            logger.info("DRY RUN MODE - No changes will be made to Shelly device")
            logger.info("=" * 60)
        
    def clear_previous_run(self, date: str) -> None:
        """Clear all output files from a previous run for the given date"""
        daily_dir = self.file_manager._get_daily_dir(date)
        
        if os.path.exists(daily_dir):
            logger.info(f"Clearing previous run output from {daily_dir}")
            
            # Remove all files in the daily directory
            for filename in os.listdir(daily_dir):
                filepath = os.path.join(daily_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        logger.debug(f"Removed: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to remove {filename}: {str(e)}")
            
            logger.info("Previous run output cleared")
        else:
            logger.info(f"No previous run output found for {date}")
    
    def should_run_today(self) -> bool:
        """Check if we've already run today and handle override"""
        today = datetime.now().strftime('%Y-%m-%d')
        success_file = self.file_manager.get_success_file_path(today)
        
        if self.file_manager.file_exists(success_file):
            logger.info(f"Already processed today ({today})")
            
            # Check if force run is enabled
            force_run = os.getenv('FORCE_RUN', 'false').lower() in ('true', '1', 'yes', 'on')
            logger.info(f"FORCE_RUN environment variable: '{os.getenv('FORCE_RUN', 'false')}' -> {force_run}")
            
            if force_run:
                logger.info("Force run enabled: clearing previous run and proceeding")
                self.clear_previous_run(today)
                return True
            else:
                logger.info("Skipping due to previous successful run")
                return False
            
        logger.info(f"Not processed today ({today}), proceeding")
        return True
    
    def _write_status(
        self,
        start_time: datetime,
        status: str,
        schedules_created: int = 0,
        cheapest_hours: List[str] = None,
        target_date: str = "",
        error_message: str = None
    ) -> None:
        """Write run status to status file"""
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        run_status = RunStatus(
            timestamp=start_time.isoformat(),
            status=status,
            schedules_created=schedules_created,
            cheapest_hours=cheapest_hours or [],
            target_date=target_date,
            error_message=error_message,
            duration_seconds=duration,
            dry_run=self.dry_run
        )
        self.status_manager.write_status(run_status)

    def run(self) -> bool:
        """Main execution flow"""
        start_time = datetime.now(timezone.utc)
        try:
            logger.info("Starting cheapest hours scheduling process")

            # Step 1: Check if we should run today
            if not self.should_run_today():
                return True

            # Step 2: Fetch and analyze prices
            logger.info("Fetching electricity prices...")
            cheapest_hours = self.price_analyzer.get_cheapest_hours()
            
            if not cheapest_hours:
                logger.error("No cheapest hours found")
                self._write_status(
                    start_time=start_time,
                    status="failure",
                    error_message="No cheapest hours found"
                )
                return False
            
            logger.info(f"Found {len(cheapest_hours)} cheapest hours")
            
            # Calculate the weekday for tomorrow (when these schedules will run)
            # Get the first price point to determine the date
            first_price = cheapest_hours[0]
            dt = datetime.fromisoformat(first_price['startsAt'].replace('Z', '+00:00'))
            # Python's weekday() returns 0=Monday, but cron uses 0=Sunday
            # Convert: Python (0=Mon, 6=Sun) -> Cron (0=Sun, 1=Mon, ..., 6=Sat)
            python_weekday = dt.weekday()
            cron_weekday = (python_weekday + 1) % 7
            
            logger.info(f"Schedules will run on {dt.strftime('%A')} (weekday {cron_weekday})")
            
            # Step 3: Check if 00:00 is in cheapest hours, and if so, remove any conflicting OFF at midnight
            # This prevents a flicker when transitioning from day N 23:00 to day N+1 00:00
            # MUST happen BEFORE cleaning up old schedules!
            has_midnight_hour = any(
                datetime.fromisoformat(price['startsAt'].replace('Z', '+00:00')).hour == 0 
                for price in cheapest_hours
            )
            
            if has_midnight_hour:
                logger.info("00:00 is in cheapest hours - checking for conflicting midnight OFF schedule from previous day")
                try:
                    existing_schedules = self.schedule_manager.list_schedules()
                    removed_conflict = False
                    for schedule in existing_schedules:
                        # Parse the timespec: "0 minute hour * * weekday"
                        timespec_parts = schedule.timespec.split()
                        if len(timespec_parts) >= 6:
                            minute = timespec_parts[1]
                            hour = timespec_parts[2]
                            schedule_weekdays = timespec_parts[5]
                            
                            # Map text weekdays to numbers
                            weekday_map = {'SUN': 0, 'MON': 1, 'TUE': 2, 'WED': 3, 'THU': 4, 'FRI': 5, 'SAT': 6}
                            
                            # Check if this is an OFF at 00:00 for our target weekday
                            # Handle both numeric (1) and text (MON) formats
                            is_target_weekday = False
                            for wd in schedule_weekdays.split(','):
                                wd = wd.strip()
                                # Try numeric match
                                if wd == str(cron_weekday):
                                    is_target_weekday = True
                                    break
                                # Try text match
                                if wd.upper() in weekday_map and weekday_map[wd.upper()] == cron_weekday:
                                    is_target_weekday = True
                                    break
                            
                            if hour == "0" and minute == "0" and is_target_weekday:
                                # Check if it's an OFF command (handle both Switch.Set and switch.set)
                                for call in schedule.calls:
                                    method = call.method.lower()
                                    if method == 'switch.set' and call.params.get('on') is False:
                                        logger.info(f"Found conflicting OFF at 00:00 (schedule {schedule.id}, weekday {cron_weekday}, timespec={schedule.timespec}) - removing it to avoid flicker")
                                        self.schedule_manager.delete_schedule(schedule.id)
                                        removed_conflict = True
                                        break
                    if not removed_conflict:
                        logger.info("No conflicting midnight OFF schedule found (may have already been cleaned up or not exist)")
                except Exception as e:
                    logger.warning(f"Failed to check for conflicting midnight OFF: {str(e)}")
            
            # Step 4: Optionally delete old schedules
            clear_schedules = self.config.get('scheduling', {}).get('clear_old_schedules', False)
            if clear_schedules:
                # Delete all schedules except today's (today's schedules may still need to run)
                today_date = datetime.now()
                today_cron = (today_date.weekday() + 1) % 7

                # All weekdays except today
                weekdays_to_delete = [w for w in range(7) if w != today_cron]

                logger.info(f"Clearing all schedules except today ({today_date.strftime('%A')}, weekday {today_cron})")
                logger.info(f"Deleting schedules for weekdays: {weekdays_to_delete}")

                deleted_count = self.schedule_manager.delete_schedules_for_weekdays(weekdays_to_delete)
                logger.info(f"Deleted {deleted_count} old schedules")
            else:
                logger.info("Keeping existing schedules (clear_old_schedules=false)")
            
            # Step 5: Create new schedules based on price points with weekday specification
            logger.info("Creating price-based schedules with weekday specification...")

            # Prepare and log the intended schedule
            schedule_plan = []
            for price_point in cheapest_hours:
                price_start_time = datetime.fromisoformat(price_point['startsAt'].replace('Z', '+00:00'))
                end_time = price_start_time + timedelta(hours=1)
                schedule_plan.append({
                    'on_time': price_start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'off_time': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'on_hour': price_start_time.hour,
                    'on_minute': price_start_time.minute,
                    'off_hour': end_time.hour,
                    'off_minute': end_time.minute,
                    'weekday': price_start_time.strftime('%A'),
                    'cron_weekday': cron_weekday
                })
            
            # Write the schedule plan to daily subdirectory
            today = datetime.now().strftime('%Y-%m-%d')
            daily_dir = self.file_manager._get_daily_dir(today)
            plan_filename = os.path.join(daily_dir, f'schedule_plan_{datetime.now().strftime("%Y%m%dT%H%M%S")}.json')
            with open(plan_filename, 'w') as f:
                json.dump(schedule_plan, f, indent=2)

            # Create schedules with weekday specification
            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(
                price_points=cheapest_hours,
                switch_id=0,
                weekdays=[cron_weekday]
            )
            logger.info(f"Created {len(schedule_ids)} schedules for weekday {cron_weekday}")
            
            # Step 6: Save success file (skip in dry-run mode)
            today = datetime.now().strftime('%Y-%m-%d')
            result_data = {
                'date': today,
                'target_weekday': cron_weekday,
                'target_date': dt.strftime('%Y-%m-%d'),
                'cheapest_hours': cheapest_hours,
                'schedule_ids': schedule_ids,
                'consecutive_blocks': [(start.isoformat(), end.isoformat()) for start, end in consecutive_blocks],
                'created_at': datetime.now().isoformat(),
                'dry_run': self.dry_run
            }
            
            if self.dry_run:
                logger.info("=" * 60)
                logger.info("DRY RUN SUMMARY")
                logger.info("=" * 60)
                logger.info(f"Target date: {dt.strftime('%Y-%m-%d')} ({dt.strftime('%A')})")
                logger.info(f"Cheapest hours found: {len(cheapest_hours)}")
                logger.info(f"Consecutive blocks: {len(consecutive_blocks)}")
                for i, (start, end) in enumerate(consecutive_blocks):
                    duration = (end - start).total_seconds() / 3600
                    logger.info(f"  Block {i+1}: {start.strftime('%H:%M')} - {end.strftime('%H:%M')} ({duration:.0f}h)")
                logger.info(f"Schedules that would be created: {len(schedule_ids)}")
                logger.info("=" * 60)
                logger.info("[DRY RUN] Skipping success file write")
            else:
                self.file_manager.write_result_file(today, result_data)
                self.file_manager.write_success_file(today)
            
            # Extract hour strings for status tracking
            cheapest_hour_strings = [
                datetime.fromisoformat(price['startsAt'].replace('Z', '+00:00')).strftime('%H:%M')
                for price in cheapest_hours
            ]

            self._write_status(
                start_time=start_time,
                status="success",
                schedules_created=len(schedule_ids),
                cheapest_hours=cheapest_hour_strings,
                target_date=dt.strftime('%Y-%m-%d')
            )

            logger.info("Successfully completed scheduling process")
            return True

        except Exception as e:
            logger.exception(f"Failed to complete scheduling process: {str(e)}")
            self._write_status(
                start_time=start_time,
                status="failure",
                error_message=str(e)
            )
            return False

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Schedule electricity usage during cheapest hours'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Run without making changes to Shelly device (fetch prices, calculate schedules, but skip device API calls)'
    )
    args = parser.parse_args()
    
    # Also check environment variable for dry-run
    dry_run = args.dry_run or os.getenv('DRY_RUN', 'false').lower() in ('true', '1', 'yes', 'on')
    
    try:
        # Load configuration
        config = get_config()
        
        # Set debug level if enabled
        if config['tibber']['debug']:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        
        # Create scheduler and run
        scheduler = CheapestHoursScheduler(config, dry_run=dry_run)
        success = scheduler.run()
        
        if success:
            logger.info("Scheduling process completed successfully")
            sys.exit(0)
        else:
            logger.error("Scheduling process failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 