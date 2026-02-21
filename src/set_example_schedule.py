#!/usr/bin/env python3
"""
Set a static example schedule on the Shelly device for development/demo purposes.
"""

import os
import sys
import logging
from typing import Dict, Any

from src.shelly_schedule import ShellyScheduleManager
from src.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point"""
    try:
        # Load configuration
        config = get_config()
        
        # Set debug level if enabled
        if config['tibber']['debug']:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        
        # Create schedule manager
        schedule_manager = ShellyScheduleManager(
            shelly_host=config['shelly']['host'],
            timeout=config['shelly']['timeout'],
            debug=config['tibber']['debug']
        )
        
        logger.info(f"Connecting to Shelly device at {config['shelly']['host']}")
        
        # Test connection first
        if not schedule_manager.test_connection():
            logger.error("Cannot connect to Shelly device")
            sys.exit(1)
        
        logger.info("✅ Connected to Shelly device successfully")
        
        # Delete all existing schedules
        logger.info("Deleting all existing schedules...")
        revision = schedule_manager.delete_all_schedules()
        logger.info(f"✅ Deleted all schedules (revision: {revision})")
        
        # Set static example schedule
        logger.info("Setting static example schedule:")
        
        # Example: ON at 08:00, OFF at 10:00
        on_schedule_id = schedule_manager.create_switch_schedule(
            hour=8, 
            minute=0, 
            turn_on=True
        )
        logger.info(f"  Created ON schedule {on_schedule_id} for 08:00")
        
        off_schedule_id = schedule_manager.create_switch_schedule(
            hour=10, 
            minute=0, 
            turn_on=False
        )
        logger.info(f"  Created OFF schedule {off_schedule_id} for 10:00")
        
        logger.info("✅ Example schedule set successfully")
        
        # List the created schedules
        logger.info("Current schedules:")
        existing_schedules = schedule_manager.list_schedules()
        for schedule in existing_schedules:
            logger.info(f"  - ID: {schedule.id}, Timespec: {schedule.timespec}")
        
    except Exception as e:
        logger.error(f"Failed to set example schedule: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 