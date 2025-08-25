"""Idle detection and management for employees"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

class IdleDetector:
    """Detect and manage idle periods for employees"""
    
    def __init__(self):
        self.db = DatabaseManager()
    
    def calculate_dynamic_idle_threshold(self, role_id: int, items_count: int) -> int:
        """Calculate dynamic idle threshold for batch work
        
        Args:
            role_id: The role configuration ID
            items_count: Number of items in the batch
            
        Returns:
            Idle threshold in minutes
        """
        # Get role configuration
        role_config = self.db.execute_one(
            """
            SELECT role_type, expected_per_hour, idle_threshold_minutes 
            FROM role_configs 
            WHERE id = %s
            """,
            (role_id,)
        )
        
        if not role_config:
            return 7  # Default fallback
        
        # For continuous work, use fixed threshold
        if role_config['role_type'] == 'continuous':
            return role_config['idle_threshold_minutes']
        
        # For batch work, calculate dynamic threshold
        # Time per item in minutes
        time_per_item = 60.0 / role_config['expected_per_hour']
        
        # Calculate with 10% buffer
        dynamic_threshold = items_count * time_per_item * 1.1
        
        # Apply minimum of 3 minutes, no maximum
        return max(3, int(dynamic_threshold))
    
    def check_real_time_idle(self, employee_id: int) -> Optional[Dict]:
        """Check if an employee is currently idle"""
        # Get employee info
        employee = self.db.execute_one(
            """
            SELECT 
                e.id,
                e.name,
                rc.role_name,
                rc.idle_threshold_minutes,
                rc.id as role_id
            FROM employees e
            LEFT JOIN (
                SELECT employee_id, role_id
                FROM activity_logs
                WHERE employee_id = %s
                AND DATE(window_start) = CURDATE()
                ORDER BY window_start DESC
                LIMIT 1
            ) latest_activity ON latest_activity.employee_id = e.id
            LEFT JOIN role_configs rc ON rc.id = COALESCE(latest_activity.role_id, 3)
            WHERE e.id = %s
            """,
            (employee_id, employee_id)
        )
        
        if not employee:
            return None
        
        # Get current clock status
        current_clock = self.db.execute_one(
            """
            SELECT clock_in, clock_out
            FROM clock_times
            WHERE employee_id = %s
            AND DATE(clock_in) = CURDATE()
            ORDER BY clock_in DESC
            LIMIT 1
            """,
            (employee_id,)
        )
        
        if not current_clock or current_clock['clock_out']:
            # Not clocked in
            return None
        
        # Get last activity with items count
        last_activity = self.db.execute_one(
            """
            SELECT 
                window_end,
                role_id,
                items_count,
                activity_type
            FROM activity_logs
            WHERE employee_id = %s
            AND DATE(window_start) = CURDATE()
            ORDER BY window_end DESC
            LIMIT 1
            """,
            (employee_id,)
        )
        
        # Calculate idle threshold
        if last_activity and last_activity['role_id'] in [3, 4, 5]:  # Batch work roles
            idle_threshold = self.calculate_dynamic_idle_threshold(
                last_activity['role_id'], 
                last_activity['items_count']
            )
        else:
            idle_threshold = employee['idle_threshold_minutes']
        
        if not last_activity:
            # No activity since clock in
            clock_in_time = current_clock['clock_in']
            idle_minutes = (datetime.now() - clock_in_time).total_seconds() / 60
            
            if idle_minutes > idle_threshold:
                return {
                    'employee_id': employee_id,
                    'employee_name': employee['name'],
                    'role': employee['role_name'],
                    'idle_since': clock_in_time,
                    'idle_minutes': int(idle_minutes),
                    'threshold': idle_threshold,
                    'status': 'idle_since_clock_in'
                }
        else:
            # Check time since last activity
            last_activity_time = last_activity['window_end']
            idle_minutes = (datetime.now() - last_activity_time).total_seconds() / 60
            
            if idle_minutes > idle_threshold:
                # Check if already recorded
                existing = self.db.execute_one(
                    """
                    SELECT * FROM idle_periods
                    WHERE employee_id = %s
                    AND start_time = %s
                    AND end_time IS NULL
                    """,
                    (employee_id, last_activity_time)
                )
                
                if not existing:
                    # Record new idle period
                    self.db.execute_update(
                        """
                        INSERT INTO idle_periods (employee_id, start_time, duration_minutes)
                        VALUES (%s, %s, %s)
                        """,
                        (employee_id, last_activity_time, int(idle_minutes))
                    )
                    
                    # Create alert
                    self._create_idle_alert(employee, idle_minutes, idle_threshold, last_activity)
                
                return {
                    'employee_id': employee_id,
                    'employee_name': employee['name'],
                    'role': employee['role_name'],
                    'idle_since': last_activity_time,
                    'idle_minutes': int(idle_minutes),
                    'threshold': idle_threshold,
                    'status': 'idle_after_activity',
                    'last_activity': f"{last_activity['activity_type']} ({last_activity['items_count']} items)"
                }
        
        return None
    
    def _create_idle_alert(self, employee: Dict, idle_minutes: int, threshold: int, last_activity: Dict = None):
        """Create an alert for idle period"""
        activity_info = ""
        if last_activity:
            activity_info = f" after {last_activity['activity_type']} ({last_activity['items_count']} items)"
        
        message = (
            f"{employee['name']} has been idle for {int(idle_minutes)} minutes "
            f"(threshold: {threshold} minutes){activity_info}"
        )
        
        severity = 'warning'
        if idle_minutes > threshold * 1.5:  # Critical at 150% of threshold
            severity = 'critical'
            message = "URGENT: " + message
        
        self.db.execute_update(
            """
            INSERT INTO alerts (employee_id, alert_type, severity, message)
            VALUES (%s, %s, %s, %s)
            """,
            (employee['id'], 'idle_detected', severity, message)
        )
    
    def check_all_employees_idle(self) -> List[Dict]:
        """Check all currently clocked-in employees for idle status"""
        # Get all clocked-in employees
        clocked_in = self.db.execute_query(
            """
            SELECT DISTINCT e.id
            FROM employees e
            JOIN clock_times ct ON ct.employee_id = e.id
            WHERE DATE(ct.clock_in) = CURDATE()
            AND ct.clock_out IS NULL
            AND e.is_active = 1
            """
        )
        
        idle_employees = []
        for employee in clocked_in:
            idle_status = self.check_real_time_idle(employee['id'])
            if idle_status:
                idle_employees.append(idle_status)
        
        return idle_employees
    
    def get_idle_summary(self, date: datetime.date) -> Dict:
        """Get summary of idle periods for a date"""
        summary = self.db.execute_query(
            """
            SELECT 
                e.name,
                COUNT(*) as idle_count,
                SUM(ip.duration_minutes) as total_idle_minutes,
                AVG(ip.duration_minutes) as avg_idle_minutes
            FROM idle_periods ip
            JOIN employees e ON e.id = ip.employee_id
            WHERE DATE(ip.start_time) = %s
            GROUP BY e.id, e.name
            ORDER BY total_idle_minutes DESC
            """,
            (date,)
        )
        
        return {
            'date': date,
            'employees': summary,
            'total_employees_with_idle': len(summary),
            'total_idle_periods': sum(emp['idle_count'] for emp in summary)
        }
