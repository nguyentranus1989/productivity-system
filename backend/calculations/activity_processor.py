"""Process and aggregate activity data"""
from datetime import datetime, timedelta
from typing import Dict, List
import logging
from collections import defaultdict

from database.db_manager import get_db
from utils.timezone_helpers import TimezoneHelper

logger = logging.getLogger(__name__)

class ActivityProcessor:
    """Process and aggregate activity data in real-time"""

    def __init__(self):
        self.db = get_db()
        self.tz_helper = TimezoneHelper()
    
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
        now = self.tz_helper.get_current_ct_date()
        ct_now = datetime.now(self.tz_helper.central_tz)
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(now)

        # Get today's stats (using UTC range for index optimization)
        today_stats = self.db.execute_one(
            """
            SELECT
                COALESCE(SUM(items_count), 0) as items_today,
                COUNT(DISTINCT window_start) as windows_active,
                MAX(window_end) as last_activity
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s AND window_start < %s
            """,
            (employee_id, utc_start, utc_end)
        )

        # Get current hour stats (CT hour boundaries)
        hour_start_ct = ct_now.replace(minute=0, second=0, microsecond=0)
        hour_start_utc = hour_start_ct.astimezone(self.tz_helper.utc_tz)
        hour_stats = self.db.execute_one(
            """
            SELECT
                COALESCE(SUM(items_count), 0) as items_this_hour,
                COUNT(*) as activities_this_hour
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s
            """,
            (employee_id, hour_start_utc)
        )

        # Get current score (use CT date parameter)
        current_score = self.db.execute_one(
            """
            SELECT
                points_earned,
                efficiency_rate,
                active_minutes,
                clocked_minutes
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date = %s
            """,
            (employee_id, now)
        )
        
        return {
            'timestamp': ct_now,
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
        ct_date = self.tz_helper.get_current_ct_date()
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(ct_date)

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

        # Check for unusually high item counts (using UTC range)
        high_count_activities = self.db.execute_query(
            """
            SELECT * FROM activity_logs
            WHERE employee_id = %s
            AND items_count > %s
            AND window_start >= %s AND window_start < %s
            """,
            (employee_id, role_info['expected_per_hour'] * 0.5, utc_start, utc_end)
        )

        for activity in high_count_activities:
            anomalies.append({
                'type': 'high_item_count',
                'activity_id': activity['id'],
                'items': activity['items_count'],
                'expected_max': role_info['expected_per_hour'] // 6,
                'window_start': activity['window_start']
            })

        # Check for duplicate windows (using UTC range)
        duplicates = self.db.execute_query(
            """
            SELECT window_start, COUNT(*) as count
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= %s AND window_start < %s
            GROUP BY window_start
            HAVING COUNT(*) > 1
            """,
            (employee_id, utc_start, utc_end)
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
        ct_date = self.tz_helper.get_current_ct_date()
        ct_now = datetime.now(self.tz_helper.central_tz)
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(ct_date)

        where_clause = "WHERE e.is_active = TRUE"
        params = [utc_start, utc_end]

        if role_id:
            where_clause += " AND e.role_id = %s"
            params.append(role_id)

        # Get team stats (using UTC range for index optimization)
        team_stats = self.db.execute_one(
            f"""
            SELECT
                COUNT(DISTINCT a.employee_id) as active_employees,
                COALESCE(SUM(a.items_count), 0) as total_items,
                COUNT(DISTINCT a.window_start) as total_windows
            FROM employees e
            LEFT JOIN activity_logs a ON e.id = a.employee_id
                AND a.window_start >= %s AND a.window_start < %s
            {where_clause}
            """,
            params
        )

        # Get efficiency stats (use CT date parameter)
        score_params = [ct_date]
        if role_id:
            score_params.append(role_id)

        efficiency_stats = self.db.execute_one(
            f"""
            SELECT
                AVG(ds.efficiency_rate) as avg_efficiency,
                MIN(ds.efficiency_rate) as min_efficiency,
                MAX(ds.efficiency_rate) as max_efficiency,
                SUM(ds.points_earned) as total_points
            FROM employees e
            JOIN daily_scores ds ON e.id = ds.employee_id
                AND ds.score_date = %s
            {where_clause}
            """,
            score_params
        )

        return {
            'timestamp': ct_now,
            'active_employees': team_stats['active_employees'],
            'total_items': team_stats['total_items'],
            'total_windows': team_stats['total_windows'],
            'avg_efficiency': efficiency_stats['avg_efficiency'] or 0,
            'min_efficiency': efficiency_stats['min_efficiency'] or 0,
            'max_efficiency': efficiency_stats['max_efficiency'] or 0,
            'total_points': efficiency_stats['total_points'] or 0
        }
