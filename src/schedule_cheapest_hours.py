#!/usr/bin/env python3
"""
Cheapest Hours Scheduler
Main orchestrator for scheduling electricity usage during cheapest hours
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from price_analysis import PriceAnalyzer
from file_io import FileManager
from shelly_schedule import ShellyScheduleManager
from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CheapestHoursScheduler:
    """Main orchestrator for scheduling cheapest hours"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.price_analyzer = PriceAnalyzer(config)
        self.file_manager = FileManager()
        self.schedule_manager = ShellyScheduleManager(
            shelly_host=config['shelly']['host'],
            timeout=config['shelly']['timeout']
        )
        
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
            force_run = os.getenv('FORCE_RUN', 'false').lower() == 'true'
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
    
    def run(self) -> bool:
        """Main execution flow"""
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
                return False
            
            logger.info(f"Found {len(cheapest_hours)} cheapest hours")
            
            # Step 3: Delete existing schedules
            logger.info("Clearing existing schedules...")
            self.schedule_manager.delete_all_schedules()
            
            # Step 4: Create new schedules based on price points
            logger.info("Creating price-based schedules...")

            # Prepare and log the intended schedule
            schedule_plan = []
            for price_point in cheapest_hours:
                from datetime import datetime, timedelta
                start_time = datetime.fromisoformat(price_point['startsAt'].replace('Z', '+00:00'))
                end_time = start_time + timedelta(hours=1)
                schedule_plan.append({
                    'on_time': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'off_time': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'on_hour': start_time.hour,
                    'on_minute': start_time.minute,
                    'off_hour': end_time.hour,
                    'off_minute': end_time.minute
                })
            
            # Write the schedule plan to daily subdirectory
            today = datetime.now().strftime('%Y-%m-%d')
            daily_dir = self.file_manager._get_daily_dir(today)
            plan_filename = os.path.join(daily_dir, f'schedule_plan_{datetime.now().strftime("%Y%m%dT%H%M%S")}.json')
            with open(plan_filename, 'w') as f:
                json.dump(schedule_plan, f, indent=2)

            schedule_ids, consecutive_blocks = self.schedule_manager.create_price_based_schedules(
                price_points=cheapest_hours,
                switch_id=0
            )
            logger.info(f"Created {len(schedule_ids)} schedules")
            
            # Step 5: Save success file
            today = datetime.now().strftime('%Y-%m-%d')
            result_data = {
                'date': today,
                'cheapest_hours': cheapest_hours,
                'schedule_ids': schedule_ids,
                'consecutive_blocks': [(start.isoformat(), end.isoformat()) for start, end in consecutive_blocks],
                'created_at': datetime.now().isoformat()
            }
            
            self.file_manager.write_result_file(today, result_data)
            self.file_manager.write_success_file(today)
            
            logger.info("Successfully completed scheduling process")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete scheduling process: {str(e)}")
            return False

def main():
    """Main entry point"""
    try:
        # Load configuration
        config = get_config()
        
        # Set debug level if enabled
        if config['tibber']['debug']:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        
        # Create scheduler and run
        scheduler = CheapestHoursScheduler(config)
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