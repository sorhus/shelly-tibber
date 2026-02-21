#!/usr/bin/env python3
"""
Type Definitions Module
Provides dataclasses and type hints for configuration and API responses
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


# =============================================================================
# Configuration Types
# =============================================================================

@dataclass
class TibberConfig:
    """Tibber API configuration"""
    token: str
    home_id: str
    debug: bool = False


@dataclass
class ShellyConfig:
    """Shelly device configuration"""
    host: str
    timeout: int = 10
    username: str = ""
    password: str = ""


@dataclass
class PriceThresholdConfig:
    """Price threshold configuration for additional scheduling"""
    enabled: bool = False
    monthly_thresholds: Dict[str, float] = field(default_factory=dict)


@dataclass
class SchedulingConfig:
    """Scheduling behavior configuration"""
    num_cheapest_hours: int = 10
    clear_old_schedules: bool = False
    price_threshold: PriceThresholdConfig = field(default_factory=PriceThresholdConfig)


@dataclass
class AppConfig:
    """Complete application configuration"""
    tibber: TibberConfig
    shelly: ShellyConfig
    scheduling: SchedulingConfig = field(default_factory=SchedulingConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create AppConfig from a dictionary (e.g., loaded from JSON)"""
        # Parse price threshold config
        price_threshold_data = data.get("scheduling", {}).get("price_threshold", {})
        price_threshold = PriceThresholdConfig(
            enabled=price_threshold_data.get("enabled", False),
            monthly_thresholds=price_threshold_data.get("monthly_thresholds", {})
        )

        # Parse scheduling config
        scheduling = SchedulingConfig(
            num_cheapest_hours=data.get("scheduling", {}).get("num_cheapest_hours", 10),
            clear_old_schedules=data.get("scheduling", {}).get("clear_old_schedules", False),
            price_threshold=price_threshold
        )

        return cls(
            tibber=TibberConfig(
                token=data.get("tibber", {}).get("token", ""),
                home_id=data.get("tibber", {}).get("home_id", ""),
                debug=data.get("tibber", {}).get("debug", False)
            ),
            shelly=ShellyConfig(
                host=data.get("shelly", {}).get("host", ""),
                timeout=data.get("shelly", {}).get("timeout", 10),
                username=data.get("shelly", {}).get("username", ""),
                password=data.get("shelly", {}).get("password", "")
            ),
            scheduling=scheduling
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert AppConfig to a dictionary"""
        return {
            "tibber": {
                "token": self.tibber.token,
                "home_id": self.tibber.home_id,
                "debug": self.tibber.debug
            },
            "shelly": {
                "host": self.shelly.host,
                "timeout": self.shelly.timeout,
                "username": self.shelly.username,
                "password": self.shelly.password
            },
            "scheduling": {
                "num_cheapest_hours": self.scheduling.num_cheapest_hours,
                "clear_old_schedules": self.scheduling.clear_old_schedules,
                "price_threshold": {
                    "enabled": self.scheduling.price_threshold.enabled,
                    "monthly_thresholds": self.scheduling.price_threshold.monthly_thresholds
                }
            }
        }


# =============================================================================
# Tibber API Response Types
# =============================================================================

@dataclass
class PricePoint:
    """A single hourly price point from Tibber"""
    starts_at: datetime
    total: float  # Total price including all fees
    energy: float  # Spot price only

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PricePoint":
        """Create PricePoint from Tibber API response dict"""
        starts_at_str = data.get("startsAt", "")
        # Handle both 'Z' suffix and '+00:00' format
        if starts_at_str.endswith('Z'):
            starts_at_str = starts_at_str.replace('Z', '+00:00')
        
        return cls(
            starts_at=datetime.fromisoformat(starts_at_str),
            total=data.get("total", 0.0),
            energy=data.get("energy", data.get("total", 0.0))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format compatible with existing code"""
        return {
            "startsAt": self.starts_at.isoformat(),
            "total": self.total,
            "energy": self.energy
        }


@dataclass
class Address:
    """Tibber home address"""
    address1: str
    postal_code: str
    city: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Address":
        return cls(
            address1=data.get("address1", ""),
            postal_code=data.get("postalCode", ""),
            city=data.get("city", "")
        )


@dataclass
class TibberHome:
    """A Tibber home with price information"""
    id: str
    address: Address
    tomorrow_prices: List[PricePoint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TibberHome":
        """Create TibberHome from API response"""
        address = Address.from_dict(data.get("address", {}))
        
        # Extract tomorrow's prices
        price_info = data.get("currentSubscription", {}).get("priceInfo", {})
        tomorrow_data = price_info.get("tomorrow") or []
        tomorrow_prices = [PricePoint.from_dict(p) for p in tomorrow_data]
        
        return cls(
            id=data.get("id", ""),
            address=address,
            tomorrow_prices=tomorrow_prices
        )


# =============================================================================
# Shelly Types
# =============================================================================

@dataclass
class ShellyScheduleCall:
    """A method call within a Shelly schedule"""
    method: str
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShellyScheduleCall":
        return cls(
            method=data.get("method", ""),
            params=data.get("params", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "params": self.params
        }


@dataclass
class ShellySchedule:
    """A schedule on a Shelly device"""
    id: Optional[int] = None
    enable: bool = True
    timespec: str = ""
    calls: List[ShellyScheduleCall] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShellySchedule":
        calls = [ShellyScheduleCall.from_dict(c) for c in data.get("calls", [])]
        return cls(
            id=data.get("id"),
            enable=data.get("enable", True),
            timespec=data.get("timespec", ""),
            calls=calls
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "enable": self.enable,
            "timespec": self.timespec,
            "calls": [c.to_dict() for c in self.calls]
        }


# =============================================================================
# Result Types
# =============================================================================

@dataclass
class ScheduleBlock:
    """A consecutive block of scheduled hours"""
    start: datetime
    end: datetime

    @property
    def duration_hours(self) -> float:
        """Duration of the block in hours"""
        return (self.end - self.start).total_seconds() / 3600


# =============================================================================
# Energy Analysis Types
# =============================================================================

@dataclass
class HourlyEnergyUsage:
    """Energy usage data for a specific hour"""
    date: str
    hour: int
    consumption: float  # kWh
    cost: float  # SEK
    price: float  # SEK/kWh
    was_scheduled: bool = False


@dataclass
class DailyEnergySummary:
    """Summary of energy usage for a single day"""
    date: str
    total_consumption: float  # kWh
    total_cost: float  # SEK
    scheduled_consumption: float  # kWh during scheduled hours
    scheduled_cost: float  # SEK during scheduled hours
    scheduled_hours: int  # Number of scheduled hours
    total_hours: int  # Total hours with data

    @property
    def efficiency_ratio(self) -> float:
        """Ratio of scheduled consumption to total consumption"""
        if self.total_consumption > 0:
            return self.scheduled_consumption / self.total_consumption
        return 0.0
