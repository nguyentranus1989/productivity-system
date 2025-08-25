"""Process and aggregate activity data"""
from datetime import datetime, timedelta
from typing import Dict, List
import logging
from collections import defaultdict

from database.db_manager import get_db

logger = logging.getLogger(__name__)

class ActivityProcessor:
    """Process and aggregate activity data in real-time"""
    
    def __init__(self):
        self.db = get_db()
    
    def aggregate_activities_by_window(self, employee_id: int, start_time: datetime, 
                                     end_time: datetime) -> List[Dict]:
        """Aggregate activities within a time window"""
        activities = self.db.execute_query(
            """
            SELECT 
                role_id,
                window_start,
                window_end,
                SUM(items_count) as total_items,
                COUNT(*) as activity_count
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s
            AND window_end <= %s
            GROUP BY role_id, window_start, window_end
            ORDER BY window_start
            """,
            (employee_id, start_time, end_time)
        )
        
        return activities
    
    def get_real_time_stats(self, employee_id: int) -> Dict:
        """Get real-time statistics for an employee"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get today's stats
        today_stats = self.db.execute_one(
            """
            SELECT 
                COALESCE(SUM(items_count), 0) as items_today,
                COUNT(DISTINCT window_start) as windows_active,
                MAX(window_end) as last_activity
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s
            """,
            (employee_id, today_start)
        )
        
        # Get current hour stats
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        hour_stats = self.db.execute_one(
            """
            SELECT 
                COALESCE(SUM(items_count), 0) as items_this_hour,
                COUNT(*) as activities_this_hour
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s
            """,
            (employee_id, hour_start)
        )
        
        # Get current score
        current_score = self.db.execute_one(
            """
            SELECT 
                points_earned,
                efficiency_rate,
                active_minutes,
                clocked_minutes
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date = CURDATE()
            """,
            (employee_id,)
        )
        
        return {
            'timestamp': now,
            'items_today': today_stats['items_today'],
            'windows_active': today_stats['windows_active'],
            'last_activity': today_stats['last_activity'],
            'items_this_hour': hour_stats['items_this_hour'],
            'current_points': current_score['points_earned'] if current_score else 0,
            'current_efficiency': current_score['efficiency_rate'] if current_score else 0,
            'active_minutes': current_score['active_minutes'] if current_score else 0,
            'clocked_minutes': current_score['clocked_minutes'] if current_score else 0
        }
    
    def detect_anomalies(self, employee_id: int) -> List[Dict]:
        """Detect anomalies in activity patterns"""
        anomalies = []
        
        # Get employee's role config
        role_info = self.db.execute_one(
            """
            SELECT rc.* 
            FROM employees e
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE e.id = %s
            """,
            (employee_id,)
        )
        
        if not role_info:
            return anomalies
        
        # Check for unusually high item counts
        high_count_activities = self.db.execute_query(
            """
            SELECT * FROM activity_logs
            WHERE employee_id = %s
            AND items_count > %s
            AND DATE(window_start) = CURDATE()
            """,
            (employee_id, role_info['expected_per_hour'] * 0.5)  # More than half hourly rate in 10 min
        )
        
        for activity in high_count_activities:
            anomalies.append({
                'type': 'high_item_count',
                'activity_id': activity['id'],
                'items': activity['items_count'],
                'expected_max': role_info['expected_per_hour'] // 6,
                'window_start': activity['window_start']
            })
        
        # Check for duplicate windows
        duplicates = self.db.execute_query(
            """
            SELECT window_start, COUNT(*) as count
            FROM activity_logs
            WHERE employee_id = %s
            AND DATE(window_start) = CURDATE()
            GROUP BY window_start
            HAVING COUNT(*) > 1
            """,
            (employee_id,)
        )
        
        for dup in duplicates:
            anomalies.append({
                'type': 'duplicate_window',
                'window_start': dup['window_start'],
                'count': dup['count']
            })
        
        return anomalies
    
    def get_team_real_time_stats(self, role_id: int = None) -> Dict:
        """Get real-time statistics for a team/role"""
        where_clause = "WHERE e.is_active = TRUE"
        params = []
        
        if role_id:
            where_clause += " AND e.role_id = %s"
            params.append(role_id)
        
        # Get team stats
        team_stats = self.db.execute_one(
            f"""
            SELECT 
                COUNT(DISTINCT a.employee_id) as active_employees,
                COALESCE(SUM(a.items_count), 0) as total_items,
                COUNT(DISTINCT a.window_start) as total_windows
            FROM employees e
            LEFT JOIN activity_logs a ON e.id = a.employee_id
                AND DATE(a.window_start) = CURDATE()
            {where_clause}
            """,
            params
        )
        
        # Get efficiency stats
        efficiency_stats = self.db.execute_one(
            f"""
            SELECT 
                AVG(ds.efficiency_rate) as avg_efficiency,
                MIN(ds.efficiency_rate) as min_efficiency,
                MAX(ds.efficiency_rate) as max_efficiency,
                SUM(ds.points_earned) as total_points
            FROM employees e
            JOIN daily_scores ds ON e.id = ds.employee_id
                AND ds.score_date = CURDATE()
            {where_clause}
            """,
            params
        )
        
        return {
            'timestamp': datetime.now(),
            'active_employees': team_stats['active_employees'],
            'total_items': team_stats['total_items'],
            'total_windows': team_stats['total_windows'],
            'avg_efficiency': efficiency_stats['avg_efficiency'] or 0,
            'min_efficiency': efficiency_stats['min_efficiency'] or 0,
            'max_efficiency': efficiency_stats['max_efficiency'] or 0,
            'total_points': efficiency_stats['total_points'] or 0
        }
