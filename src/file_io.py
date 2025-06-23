#!/usr/bin/env python3
"""
File I/O Management Module
Handles reading, writing, and managing result files with daily subdirectories
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FileManager:
    """Manages file operations for the application"""
    
    def __init__(self, base_output_dir: str = "output"):
        self.base_output_dir = base_output_dir
        self.logger = logging.getLogger(__name__)
        
    def _get_daily_dir(self, date: str) -> str:
        """Get the daily subdirectory path for a given date"""
        daily_dir = os.path.join(self.base_output_dir, date)
        os.makedirs(daily_dir, exist_ok=True)
        return daily_dir
    
    def write_result_file(self, date: str, data: Dict[str, Any]) -> str:
        """Write result data to a JSON file in the daily subdirectory"""
        daily_dir = self._get_daily_dir(date)
        filename = f"result_{date}.json"
        filepath = os.path.join(daily_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Result file written: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Failed to write result file: {str(e)}")
            raise
    
    def read_result_file(self, date: str) -> Dict[str, Any]:
        """Read result data from a JSON file in the daily subdirectory"""
        daily_dir = self._get_daily_dir(date)
        filename = f"result_{date}.json"
        filepath = os.path.join(daily_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self.logger.info(f"Result file read: {filepath}")
            return data
        except FileNotFoundError:
            self.logger.warning(f"Result file not found: {filepath}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to read result file: {str(e)}")
            raise
    
    def file_exists(self, filepath: str) -> bool:
        """Check if a file exists"""
        return os.path.exists(filepath)
    
    def get_success_file_path(self, date: str) -> str:
        """Get the path for the success file in the daily subdirectory"""
        daily_dir = self._get_daily_dir(date)
        return os.path.join(daily_dir, f"success_{date}.txt")
    
    def write_success_file(self, date: str) -> str:
        """Write a success file to indicate completion for a given date"""
        success_file = self.get_success_file_path(date)
        
        try:
            with open(success_file, 'w') as f:
                f.write(f"Successfully processed on {datetime.now().isoformat()}\n")
            self.logger.info(f"Success file written: {success_file}")
            return success_file
        except Exception as e:
            self.logger.error(f"Failed to write success file: {str(e)}")
            raise
    
    def replace_result_file(self, date: str, data: Dict[str, Any]) -> str:
        """Replace existing result file with new data"""
        return self.write_result_file(date, data)
    
    def cleanup_old_files(self, days_to_keep: int = 7) -> int:
        """Clean up old daily directories and files"""
        try:
            import shutil
            
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            deleted_count = 0
            
            if not os.path.exists(self.base_output_dir):
                return 0
            
            for item in os.listdir(self.base_output_dir):
                item_path = os.path.join(self.base_output_dir, item)
                
                # Check if it's a directory and try to parse as date
                if os.path.isdir(item_path):
                    try:
                        item_date = datetime.strptime(item, '%Y-%m-%d')
                        if item_date < cutoff_date:
                            shutil.rmtree(item_path)
                            self.logger.info(f"Deleted old directory: {item_path}")
                            deleted_count += 1
                    except ValueError:
                        # Not a date directory, skip
                        continue
            
            self.logger.info(f"Cleanup completed: {deleted_count} old directories removed")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old files: {str(e)}")
            return 0 