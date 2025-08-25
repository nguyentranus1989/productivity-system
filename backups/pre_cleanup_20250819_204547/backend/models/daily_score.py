"""Daily score model"""
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass

@dataclass
class DailyScore:
    """Daily productivity score data model"""
    id: Optional[int] = None
    employee_id: int = None
    employee_name: Optional[str] = None  # Joined from employees
    score_date: date = None
    items_processed: int = 0
    active_minutes: int = 0
    clocked_minutes: int = 0
    efficiency_rate: float = 0.0
    points_earned: float = 0.0
    is_finalized: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def efficiency_percentage(self) -> float:
        """Get efficiency as percentage"""
        return self.efficiency_rate * 100
    
    def calculate_efficiency(self) -> float:
        """Calculate efficiency rate"""
        if self.clocked_minutes > 0:
            return round(self.active_minutes / self.clocked_minutes, 2)
        return 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'score_date': self.score_date.isoformat() if self.score_date else None,
            'items_processed': self.items_processed,
            'active_minutes': self.active_minutes,
            'clocked_minutes': self.clocked_minutes,
            'efficiency_rate': self.efficiency_rate,
            'efficiency_percentage': self.efficiency_percentage,
            'points_earned': self.points_earned,
            'is_finalized': self.is_finalized
        }
