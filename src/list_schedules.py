#!/usr/bin/env python3
"""
Script to list all schedules on Shelly device
"""

import os
import sys
import logging
from typing import Dict, Any

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from shelly_schedule import ShellyScheduleManager
from config import get_config

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
        
        # Create schedule manager
        schedule_manager = ShellyScheduleManager(
            shelly_host=config['shelly']['host'],
            timeout=config['shelly']['timeout']
        )
        
        logger.info(f"Connecting to Shelly device at {config['shelly']['host']}")
        
        # Test connection first
        if not schedule_manager.test_connection():
            logger.error("Cannot connect to Shelly device")
            sys.exit(1)
        
        logger.info("✅ Connected to Shelly device successfully")
        
        # List existing schedules
        logger.info("Fetching existing schedules...")
        existing_schedules = schedule_manager.list_schedules()
        
        if not existing_schedules:
            logger.info("No schedules found on device")
        else:
            logger.info(f"Found {len(existing_schedules)} schedules:")
            for i, schedule in enumerate(existing_schedules, 1):
                logger.info(f"  {i}. ID: {schedule.id}")
                logger.info(f"     Enabled: {schedule.enable}")
                logger.info(f"     Timespec: {schedule.timespec}")
                logger.info(f"     Calls: {schedule.calls}")
                logger.info("")
        
    except Exception as e:
        logger.error(f"Failed to list schedules: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 