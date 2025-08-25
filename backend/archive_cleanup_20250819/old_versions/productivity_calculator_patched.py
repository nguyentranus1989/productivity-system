"""Productivity calculation engine - DYNAMIC VERSION with idle fix"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import pytz

from database.db_manager import get_db, DatabaseManager
from models import Employee, RoleConfig, ActivityLog, DailyScore

logger = logging.getLogger(__name__)

class ProductivityCalculator:
    """Calculate productivity metrics for employees"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self._role_cache = {}
        self._load_role_configs()
        self.central_tz = pytz.timezone('America/Chicago')
        
    def get_central_date(self):
        """Get current date in Central Time"""
        return datetime.now(self.central_tz).date()
    
    def get_central_datetime(self):
        """Get current datetime in Central Time"""
        return datetime.now(self.central_tz)
    
    def convert_utc_to_central(self, utc_dt):
        """Convert UTC datetime to Central Time"""
        if utc_dt.tzinfo is None:
            utc_dt = pytz.UTC.localize(utc_dt)
        return utc_dt.astimezone(self.central_tz)
        
    def _load_role_configs(self):
        """Load role configurations into cache"""
        roles = self.db.execute_query("SELECT * FROM role_configs")
        for role in roles:
            self._role_cache[role['id']] = RoleConfig(**role)
        logger.info(f"Loaded {len(self._role_cache)} role configurations")
    
    def calculate_dynamic_threshold(self, role_type, items_count, expected_per_hour, idle_threshold_minutes):
        """
        Calculate threshold based on work type
        - Continuous work: Fixed threshold (5 minutes)
        - Batch work: Dynamic based on items processed
        """
        # Convert Decimal to float if needed
        if idle_threshold_minutes:
            idle_threshold_minutes = float(idle_threshold_minutes)
        if expected_per_hour:
            expected_per_hour = float(expected_per_hour)
            
        if role_type == 'batch':
            # Dynamic threshold for batch work
            if items_count and expected_per_hour and expected_per_hour > 0:
                # Time needed to process items + 5% buffer
                dynamic_threshold = items_count * (60.0 / expected_per_hour) * 1.05
                return max(dynamic_threshold, 3.0)  # Minimum 3 minutes
            else:
                return 10.0  # Default for batch with no items
        else:
            # Fixed threshold for continuous work
            return idle_threshold_minutes or 5.0
