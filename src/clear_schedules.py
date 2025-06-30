#!/usr/bin/env python3
"""
Script to clear all schedules from Shelly device
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
        
        # List existing schedules
        logger.info("Fetching existing schedules...")
        existing_schedules = schedule_manager.list_schedules()
        logger.info(f"Found {len(existing_schedules)} existing schedules")
        
        if existing_schedules:
            logger.info("Existing schedules:")
            for schedule in existing_schedules:
                logger.info(f"  - ID: {schedule.id}, Timespec: {schedule.timespec}")
        
        # Delete all schedules
        logger.info("Deleting all schedules...")
        revision = schedule_manager.delete_all_schedules()
        
        logger.info(f"✅ Successfully deleted all schedules (revision: {revision})")
        
        # Verify deletion
        remaining_schedules = schedule_manager.list_schedules()
        if not remaining_schedules:
            logger.info("✅ Verification: No schedules remaining")
        else:
            logger.warning(f"⚠️  Warning: {len(remaining_schedules)} schedules still exist")
        
    except Exception as e:
        logger.error(f"Failed to clear schedules: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 