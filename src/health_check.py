#!/usr/bin/env python3
"""
Health Check and Monitoring Module
Provides status tracking and health check functionality
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status values"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class RunStatus:
    """Status of a single scheduler run"""
    timestamp: str
    status: str  # "success", "failure", "partial"
    schedules_created: int = 0
    schedules_deleted: int = 0
    cheapest_hours: List[str] = field(default_factory=list)
    target_date: str = ""
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    dry_run: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunStatus":
        """Create RunStatus from dictionary"""
        return cls(
            timestamp=data.get("timestamp", ""),
            status=data.get("status", "unknown"),
            schedules_created=data.get("schedules_created", 0),
            schedules_deleted=data.get("schedules_deleted", 0),
            cheapest_hours=data.get("cheapest_hours", []),
            target_date=data.get("target_date", ""),
            error_message=data.get("error_message"),
            duration_seconds=data.get("duration_seconds", 0.0),
            dry_run=data.get("dry_run", False)
        )


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: HealthStatus
    message: str
    last_run: Optional[RunStatus] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "status": self.status.value,
            "message": self.message,
            "checked_at": self.checked_at,
            "details": self.details
        }
        if self.last_run:
            result["last_run"] = self.last_run.to_dict()
        return result


class StatusManager:
    """Manages status file for health monitoring"""
    
    DEFAULT_STATUS_FILE = "output/status.json"
    
    def __init__(self, status_file: Optional[str] = None):
        self.status_file = status_file or self.DEFAULT_STATUS_FILE
    
    def _ensure_directory(self) -> None:
        """Ensure the directory for status file exists"""
        directory = os.path.dirname(self.status_file)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    def write_status(self, run_status: RunStatus) -> None:
        """Write run status to status file"""
        self._ensure_directory()
        
        # Read existing status to preserve history
        existing = self._read_raw_status()
        
        # Update with new status
        status_data = {
            "last_run": run_status.to_dict(),
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Keep last 10 runs in history
        history = existing.get("history", [])
        history.insert(0, run_status.to_dict())
        status_data["history"] = history[:10]
        
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
            logger.debug(f"Status written to {self.status_file}")
        except IOError as e:
            logger.error(f"Failed to write status file: {e}")
    
    def _read_raw_status(self) -> Dict[str, Any]:
        """Read raw status data from file"""
        if not os.path.exists(self.status_file):
            return {}
        
        try:
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read status file: {e}")
            return {}
    
    def get_last_run(self) -> Optional[RunStatus]:
        """Get the last run status"""
        data = self._read_raw_status()
        last_run_data = data.get("last_run")
        
        if last_run_data:
            return RunStatus.from_dict(last_run_data)
        return None
    
    def get_history(self, limit: int = 10) -> List[RunStatus]:
        """Get run history"""
        data = self._read_raw_status()
        history_data = data.get("history", [])
        
        return [RunStatus.from_dict(h) for h in history_data[:limit]]


def check_health(
    status_manager: Optional[StatusManager] = None,
    max_age_hours: int = 25
) -> HealthCheckResult:
    """
    Perform a health check on the scheduler.
    
    Args:
        status_manager: StatusManager instance (uses default if None)
        max_age_hours: Maximum age of last run before warning (default 25h for daily runs)
        
    Returns:
        HealthCheckResult with status and details
    """
    if status_manager is None:
        status_manager = StatusManager()
    
    last_run = status_manager.get_last_run()
    
    # No status file - unknown state
    if last_run is None:
        return HealthCheckResult(
            status=HealthStatus.UNKNOWN,
            message="No status information available. Scheduler may not have run yet.",
            details={"status_file": status_manager.status_file}
        )
    
    # Parse last run timestamp
    try:
        last_run_time = datetime.fromisoformat(last_run.timestamp.replace('Z', '+00:00'))
        age = datetime.now(last_run_time.tzinfo) - last_run_time
        age_hours = age.total_seconds() / 3600
    except (ValueError, AttributeError):
        age_hours = float('inf')
    
    details = {
        "last_run_age_hours": round(age_hours, 1),
        "target_date": last_run.target_date,
        "schedules_active": last_run.schedules_created,
        "cheapest_hours": last_run.cheapest_hours
    }
    
    # Check for errors
    if last_run.status == "failure":
        return HealthCheckResult(
            status=HealthStatus.ERROR,
            message=f"Last run failed: {last_run.error_message or 'Unknown error'}",
            last_run=last_run,
            details=details
        )
    
    # Check for stale data
    if age_hours > max_age_hours:
        return HealthCheckResult(
            status=HealthStatus.WARNING,
            message=f"Last run was {round(age_hours, 1)} hours ago (threshold: {max_age_hours}h)",
            last_run=last_run,
            details=details
        )
    
    # Check for partial success
    if last_run.status == "partial":
        return HealthCheckResult(
            status=HealthStatus.WARNING,
            message="Last run completed with warnings",
            last_run=last_run,
            details=details
        )
    
    # All good
    return HealthCheckResult(
        status=HealthStatus.OK,
        message=f"Healthy. Last run {round(age_hours, 1)}h ago, {last_run.schedules_created} schedules active for {last_run.target_date}",
        last_run=last_run,
        details=details
    )


def format_health_check(result: HealthCheckResult, verbose: bool = False) -> str:
    """
    Format health check result for display.
    
    Args:
        result: HealthCheckResult to format
        verbose: Include detailed information
        
    Returns:
        Formatted string for display
    """
    status_icons = {
        HealthStatus.OK: "OK",
        HealthStatus.WARNING: "WARNING",
        HealthStatus.ERROR: "ERROR",
        HealthStatus.UNKNOWN: "UNKNOWN"
    }
    
    lines = [
        f"Status: {status_icons[result.status]}",
        f"Message: {result.message}"
    ]
    
    if verbose and result.last_run:
        lines.append("")
        lines.append("Last Run Details:")
        lines.append(f"  Timestamp: {result.last_run.timestamp}")
        lines.append(f"  Status: {result.last_run.status}")
        lines.append(f"  Target Date: {result.last_run.target_date}")
        lines.append(f"  Schedules Created: {result.last_run.schedules_created}")
        lines.append(f"  Duration: {result.last_run.duration_seconds:.1f}s")
        
        if result.last_run.cheapest_hours:
            hours_str = ", ".join(result.last_run.cheapest_hours[:5])
            if len(result.last_run.cheapest_hours) > 5:
                hours_str += f" (+{len(result.last_run.cheapest_hours) - 5} more)"
            lines.append(f"  Cheapest Hours: {hours_str}")
        
        if result.last_run.dry_run:
            lines.append("  Mode: DRY RUN")
    
    return "\n".join(lines)


def health_check_cli() -> int:
    """
    CLI command for health check.
    Returns 0 for OK, 1 for WARNING, 2 for ERROR, 3 for UNKNOWN.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Check health status of shelly-tibber scheduler"
    )
    parser.add_argument(
        "--status-file",
        default=None,
        help="Path to status file (default: output/status.json)"
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=25,
        help="Maximum age of last run in hours before warning (default: 25)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    status_manager = StatusManager(args.status_file) if args.status_file else None
    result = check_health(status_manager, max_age_hours=args.max_age)
    
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_health_check(result, verbose=args.verbose))
    
    # Return exit code based on status
    exit_codes = {
        HealthStatus.OK: 0,
        HealthStatus.WARNING: 1,
        HealthStatus.ERROR: 2,
        HealthStatus.UNKNOWN: 3
    }
    return exit_codes[result.status]


if __name__ == "__main__":
    import sys
    sys.exit(health_check_cli())
