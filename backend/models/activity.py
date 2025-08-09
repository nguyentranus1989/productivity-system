"""Activity log model"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

@dataclass
class ActivityLog:
    """Activity log data model from PodFactory"""
    id: Optional[int] = None
    report_id: str = None
    employee_id: int = None
    employee_name: Optional[str] = None  # Joined from employees
    role_id: int = None
    role_name: Optional[str] = None  # Joined from role_configs
    items_count: int = 0
    window_start: datetime = None
    window_end: datetime = None
    created_at: Optional[datetime] = None
    
    @property
    def window_duration_minutes(self) -> int:
        """Calculate window duration in minutes"""
        if self.window_start and self.window_end:
            return int((self.window_end - self.window_start).total_seconds() / 60)
        return 10  # Default window is 10 minutes
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'report_id': self.report_id,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'role_id': self.role_id,
            'role_name': self.role_name,
            'items_count': self.items_count,
            'window_start': self.window_start.isoformat() if self.window_start else None,
            'window_end': self.window_end.isoformat() if self.window_end else None,
            'window_duration_minutes': self.window_duration_minutes
        }
