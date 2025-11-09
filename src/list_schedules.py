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
        
        if not existing_schedules:
            logger.info("No schedules found on device")
        else:
            logger.info(f"Found {len(existing_schedules)} schedules:")
            logger.info("")
            
            # First, show raw schedules for debugging
            logger.info("📋 Raw schedules:")
            for schedule in existing_schedules:
                logger.info(f"  ID {schedule.id}: timespec='{schedule.timespec}', calls={schedule.calls}")
            logger.info("")
            
            # Group by weekday for easier reading
            weekday_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            by_weekday = {}
            skipped = []
            
            for schedule in existing_schedules:
                # Parse timespec: '0 minute hour * * weekday'
                parts = schedule.timespec.split()
                if len(parts) < 6:
                    skipped.append(f"Schedule ID {schedule.id}: Invalid timespec format: '{schedule.timespec}'")
                    continue
                
                if len(parts) >= 6:
                    hour = parts[2]
                    minute = parts[1]
                    weekdays = parts[5]
                    
                    # Get action (ON or OFF)
                    action = '?'
                    for call in schedule.calls:
                        method = call.get('method', '').lower()
                        if method == 'switch.set':
                            action = 'ON' if call.get('params', {}).get('on') else 'OFF'
                    
                    time_str = f'{hour.zfill(2)}:{minute.zfill(2)}'
                    
                    # Map text weekdays to numbers
                    weekday_text_map = {
                        'SUN': 0, 'MON': 1, 'TUE': 2, 'WED': 3, 'THU': 4, 'FRI': 5, 'SAT': 6
                    }
                    
                    # Handle comma-separated weekdays
                    for wd in weekdays.split(','):
                        wd = wd.strip()
                        if wd == '*':
                            wd_name = 'Every day'
                        else:
                            try:
                                # Try parsing as number
                                wd_name = weekday_names[int(wd)]
                            except ValueError:
                                # Try text format (MON, TUE, etc.)
                                if wd.upper() in weekday_text_map:
                                    wd_name = weekday_names[weekday_text_map[wd.upper()]]
                                else:
                                    wd_name = f'Weekday {wd}'
                        
                        if wd_name not in by_weekday:
                            by_weekday[wd_name] = []
                        by_weekday[wd_name].append({
                            'id': schedule.id,
                            'time': time_str,
                            'action': action,
                            'enabled': schedule.enable,
                            'timespec': schedule.timespec
                        })
            
            # Show any skipped schedules
            if skipped:
                logger.info("⚠️  Skipped schedules (couldn't parse):")
                for skip_msg in skipped:
                    logger.info(f"  {skip_msg}")
                logger.info("")
            
            # Display grouped by weekday
            for wd_name in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday', 'Every day']:
                if wd_name in by_weekday:
                    logger.info(f"📅 {wd_name}:")
                    
                    # Sort by time
                    schedules_for_day = sorted(by_weekday[wd_name], key=lambda x: x['time'])
                    
                    for sched in schedules_for_day:
                        action_emoji = '🟢' if sched['action'] == 'ON' else '🔴'
                        enabled_str = '' if sched['enabled'] else ' (DISABLED)'
                        logger.info(f"  {action_emoji} {sched['action']:3s} at {sched['time']}{enabled_str}  [ID: {sched['id']}, timespec: {sched['timespec']}]")
                    logger.info("")
            
            # Check for potential issues
            logger.info("🔍 Analysis:")
            issues = []
            
            # Check for conflicts at midnight
            for wd_name, scheds in by_weekday.items():
                midnight_scheds = [s for s in scheds if s['time'] == '00:00']
                if len(midnight_scheds) > 1:
                    on_count = sum(1 for s in midnight_scheds if s['action'] == 'ON')
                    off_count = sum(1 for s in midnight_scheds if s['action'] == 'OFF')
                    if on_count > 0 and off_count > 0:
                        issues.append(f"⚠️  {wd_name}: Both ON and OFF at 00:00 - WILL FLICKER!")
            
            # Check for unbalanced ON/OFF
            for wd_name, scheds in by_weekday.items():
                actions = [s['action'] for s in scheds]
                on_count = actions.count('ON')
                off_count = actions.count('OFF')
                if on_count != off_count:
                    issues.append(f"⚠️  {wd_name}: Unbalanced ON ({on_count}) and OFF ({off_count}) schedules")
            
            if issues:
                for issue in issues:
                    logger.info(issue)
            else:
                logger.info("✅ No obvious issues detected")
            logger.info("")
        
    except Exception as e:
        logger.error(f"Failed to list schedules: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 