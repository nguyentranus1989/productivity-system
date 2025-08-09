"""Role configuration model"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class RoleType(Enum):
    CONTINUOUS = 'continuous'
    BATCH = 'batch'

@dataclass
class RoleConfig:
    """Role configuration data model"""
    id: Optional[int] = None
    role_name: str = None
    role_type: str = None  # 'continuous' or 'batch'
    multiplier: float = 1.0
    expected_per_hour: int = 0
    idle_threshold_minutes: int = 15
    monthly_target: int = 0
    seconds_per_item: Optional[int] = None  # Only for batch workers
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def is_batch_worker(self) -> bool:
        """Check if this is a batch worker role"""
        return self.role_type == RoleType.BATCH.value
    
    @property
    def is_continuous_worker(self) -> bool:
        """Check if this is a continuous worker role"""
        return self.role_type == RoleType.CONTINUOUS.value
    
    def calculate_expected_items(self, minutes: int) -> int:
        """Calculate expected items for given minutes"""
        hours = minutes / 60
        return int(self.expected_per_hour * hours)
    
    def calculate_active_time(self, items_count: int) -> int:
        """Calculate active time in seconds based on items processed"""
        if self.is_batch_worker and self.seconds_per_item:
            return items_count * self.seconds_per_item
        return 0  # Continuous workers active time calculated differently
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'role_name': self.role_name,
            'role_type': self.role_type,
            'multiplier': self.multiplier,
            'expected_per_hour': self.expected_per_hour,
            'idle_threshold_minutes': self.idle_threshold_minutes,
            'monthly_target': self.monthly_target,
            'seconds_per_item': self.seconds_per_item,
            'is_batch': self.is_batch_worker,
            'is_continuous': self.is_continuous_worker
        }
