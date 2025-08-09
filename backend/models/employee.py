"""Employee model"""
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass

@dataclass
class Employee:
    """Employee data model"""
    id: Optional[int] = None
    email: str = None
    name: str = None
    role_id: int = None
    role_name: Optional[str] = None  # Joined from role_configs
    hire_date: date = None
    is_active: bool = True
    is_new_employee: bool = True
    grace_period_end: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def days_employed(self) -> int:
        """Calculate days employed"""
        if self.hire_date:
            return (date.today() - self.hire_date).days
        return 0
    
    def is_in_grace_period(self) -> bool:
        """Check if employee is still in grace period"""
        if self.grace_period_end:
            return date.today() <= self.grace_period_end
        return False
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role_id': self.role_id,
            'role_name': self.role_name,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None,
            'is_active': self.is_active,
            'is_new_employee': self.is_new_employee,
            'grace_period_end': self.grace_period_end.isoformat() if self.grace_period_end else None,
            'days_employed': self.days_employed(),
            'in_grace_period': self.is_in_grace_period()
        }
