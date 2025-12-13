"""
Advanced Team Metrics Engine
Provides comprehensive team-level analytics and performance insights
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import statistics
from database.db_manager import DatabaseManager
from utils.timezone_helpers import TimezoneHelper

logger = logging.getLogger(__name__)

class TeamMetricsEngine:
    """Calculate and analyze team-level performance metrics"""

    def __init__(self):
        self.db_manager = DatabaseManager()
        self.tz_helper = TimezoneHelper()
    
    def get_team_overview(self, role_id: Optional[int] = None) -> Dict:
        """Get comprehensive team overview metrics"""
        ct_date = self.tz_helper.get_current_ct_date()
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(ct_date)
        week_ago = ct_date - timedelta(days=7)
        month_year = ct_date.strftime('%Y-%m')

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Build role filter
            role_filter = "AND e.role_id = %s" if role_id else ""
            base_params = [role_id] if role_id else []

            # Get team composition (using UTC range for clock_times)
            comp_params = [utc_start, utc_end, ct_date] + base_params
            cursor.execute(f"""
                SELECT
                    COUNT(DISTINCT e.id) as total_employees,
                    COUNT(DISTINCT CASE WHEN ct.clock_in IS NOT NULL THEN e.id END) as employees_present,
                    AVG(DATEDIFF(%s, e.hire_date)) as avg_tenure_days,
                    COUNT(DISTINCT CASE WHEN e.is_new_employee = TRUE THEN e.id END) as new_employees
                FROM employees e
                LEFT JOIN clock_times ct ON e.id = ct.employee_id
                    AND ct.clock_in >= %s AND ct.clock_in < %s
                WHERE e.is_active = TRUE {role_filter}
            """, [utc_start, utc_end, ct_date] + base_params)

            composition = cursor.fetchone()

            # Get today's performance (use CT date for score_date)
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ds.points_earned), 0) as total_points_today,
                    COALESCE(AVG(ds.efficiency_rate), 0) as avg_efficiency_today,
                    COALESCE(SUM(ds.items_processed), 0) as total_items_today,
                    COALESCE(AVG(ds.active_minutes), 0) as avg_active_minutes
                FROM daily_scores ds
                JOIN employees e ON ds.employee_id = e.id
                WHERE ds.score_date = %s
                AND e.is_active = TRUE {role_filter}
            """, [ct_date] + base_params)

            today_performance = cursor.fetchone()

            # Get week performance
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ds.points_earned), 0) as total_points_week,
                    COALESCE(AVG(ds.efficiency_rate), 0) as avg_efficiency_week,
                    COUNT(DISTINCT ds.employee_id) as unique_employees_week
                FROM daily_scores ds
                JOIN employees e ON ds.employee_id = e.id
                WHERE ds.score_date >= %s
                AND e.is_active = TRUE {role_filter}
            """, [week_ago] + base_params)

            week_performance = cursor.fetchone()

            # Get month performance
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ms.total_points), 0) as total_points_month,
                    COALESCE(AVG(ms.total_points / ms.target_points * 100), 0) as avg_target_completion
                FROM monthly_summaries ms
                JOIN employees e ON ms.employee_id = e.id
                WHERE ms.month_year = %s
                AND e.is_active = TRUE {role_filter}
            """, [month_year] + base_params)
            
            month_performance = cursor.fetchone()
            
            return {
                'team_composition': {
                    'total_employees': composition['total_employees'],
                    'present_today': composition['employees_present'],
                    'attendance_rate': round(composition['employees_present'] / composition['total_employees'] * 100, 1) if composition['total_employees'] > 0 else 0,
                    'avg_tenure_days': int(composition['avg_tenure_days'] or 0),
                    'new_employees': composition['new_employees']
                },
                'performance_today': {
                    'total_points': float(today_performance['total_points_today']),
                    'avg_efficiency': round(float(today_performance['avg_efficiency_today']) * 100, 1),
                    'total_items': int(today_performance['total_items_today']),
                    'avg_active_minutes': int(today_performance['avg_active_minutes'] or 0)
                },
                'performance_week': {
                    'total_points': float(week_performance['total_points_week']),
                    'avg_efficiency': round(float(week_performance['avg_efficiency_week']) * 100, 1),
                    'active_employees': week_performance['unique_employees_week']
                },
                'performance_month': {
                    'total_points': float(month_performance['total_points_month']),
                    'avg_target_completion': round(float(month_performance['avg_target_completion']), 1)
                }
            }
    
    def get_team_comparison(self) -> Dict:
        """Compare performance across different teams/roles"""
        week_ago = self.tz_helper.get_current_ct_date() - timedelta(days=7)

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Get performance by role
            cursor.execute("""
                SELECT
                    rc.id as role_id,
                    rc.role_name,
                    COUNT(DISTINCT e.id) as employee_count,
                    COALESCE(AVG(ds.points_earned), 0) as avg_points_daily,
                    COALESCE(AVG(ds.efficiency_rate), 0) as avg_efficiency,
                    COALESCE(SUM(ds.points_earned), 0) as total_points_week
                FROM role_configs rc
                LEFT JOIN employees e ON rc.id = e.role_id AND e.is_active = TRUE
                LEFT JOIN daily_scores ds ON e.id = ds.employee_id
                    AND ds.score_date >= %s
                GROUP BY rc.id, rc.role_name
                ORDER BY avg_points_daily DESC
            """, [week_ago])
            
            roles_performance = []
            for row in cursor.fetchall():
                roles_performance.append({
                    'role_id': row['role_id'],
                    'role_name': row['role_name'],
                    'employee_count': row['employee_count'],
                    'avg_points_daily': round(float(row['avg_points_daily']), 2),
                    'avg_efficiency': round(float(row['avg_efficiency']) * 100, 1),
                    'total_points_week': round(float(row['total_points_week']), 2)
                })
            
            # Calculate team rankings
            if roles_performance:
                # Rank by average daily points
                sorted_by_points = sorted(roles_performance, key=lambda x: x['avg_points_daily'], reverse=True)
                for i, role in enumerate(sorted_by_points):
                    role['points_rank'] = i + 1
                
                # Rank by efficiency
                sorted_by_efficiency = sorted(roles_performance, key=lambda x: x['avg_efficiency'], reverse=True)
                for i, role in enumerate(sorted_by_efficiency):
                    role['efficiency_rank'] = i + 1
            
            return {
                'teams': roles_performance,
                'best_performing_team': roles_performance[0]['role_name'] if roles_performance else None,
                'most_efficient_team': sorted_by_efficiency[0]['role_name'] if roles_performance else None
            }
    
    def get_team_trends(self, role_id: Optional[int] = None, days: int = 30) -> Dict:
        """Analyze team performance trends over time"""
        past_date = self.tz_helper.get_current_ct_date() - timedelta(days=days)

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            role_filter = "AND e.role_id = %s" if role_id else ""
            params = [past_date]
            if role_id:
                params.append(role_id)

            # Get daily aggregates
            cursor.execute(f"""
                SELECT
                    ds.score_date,
                    COUNT(DISTINCT ds.employee_id) as active_employees,
                    SUM(ds.points_earned) as total_points,
                    AVG(ds.efficiency_rate) as avg_efficiency,
                    SUM(ds.items_processed) as total_items,
                    AVG(ds.active_minutes) as avg_active_minutes
                FROM daily_scores ds
                JOIN employees e ON ds.employee_id = e.id
                WHERE ds.score_date >= %s
                AND e.is_active = TRUE {role_filter}
                GROUP BY ds.score_date
                ORDER BY ds.score_date
            """, params)
            
            daily_data = cursor.fetchall()
            
            if not daily_data:
                return {
                    'has_data': False,
                    'message': 'No data available for the specified period'
                }
            
            # Calculate trends
            points_by_day = [float(d['total_points']) for d in daily_data]
            efficiency_by_day = [float(d['avg_efficiency']) for d in daily_data]
            
            # Weekly averages
            weeks = defaultdict(list)
            for d in daily_data:
                week_num = d['score_date'].isocalendar()[1]
                weeks[week_num].append(float(d['total_points']))
            
            weekly_averages = []
            for week, points in sorted(weeks.items()):
                weekly_averages.append({
                    'week': week,
                    'avg_points': round(statistics.mean(points), 2)
                })
            
            # Trend direction
            if len(points_by_day) >= 14:
                recent_avg = statistics.mean(points_by_day[-7:])
                older_avg = statistics.mean(points_by_day[-14:-7])
                trend_direction = 'improving' if recent_avg > older_avg * 1.05 else 'declining' if recent_avg < older_avg * 0.95 else 'stable'
            else:
                trend_direction = 'insufficient_data'
            
            # Best and worst days
            best_day = max(daily_data, key=lambda x: x['total_points'])
            worst_day = min(daily_data, key=lambda x: x['total_points'])
            
            return {
                'has_data': True,
                'period_days': days,
                'trend_direction': trend_direction,
                'daily_average': round(statistics.mean(points_by_day), 2),
                'efficiency_average': round(statistics.mean(efficiency_by_day) * 100, 1),
                'best_day': {
                    'date': best_day['score_date'].isoformat(),
                    'points': float(best_day['total_points']),
                    'active_employees': best_day['active_employees']
                },
                'worst_day': {
                    'date': worst_day['score_date'].isoformat(),
                    'points': float(worst_day['total_points']),
                    'active_employees': worst_day['active_employees']
                },
                'weekly_averages': weekly_averages,
                'daily_data': [
                    {
                        'date': d['score_date'].isoformat(),
                        'points': float(d['total_points']),
                        'efficiency': round(float(d['avg_efficiency']) * 100, 1),
                        'active_employees': d['active_employees']
                    }
                    for d in daily_data
                ]
            }
    
    def get_shift_analysis(self) -> Dict:
        """Analyze performance by shift times"""
        week_ago = self.tz_helper.get_current_ct_date() - timedelta(days=7)
        week_ago_utc_start, _ = self.tz_helper.ct_date_to_utc_range(week_ago)

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Analyze by hour of day
            cursor.execute("""
                SELECT
                    HOUR(al.window_start) as hour,
                    COUNT(DISTINCT al.employee_id) as active_employees,
                    AVG(al.items_count) as avg_items,
                    COUNT(*) as activity_count
                FROM activity_logs al
                JOIN employees e ON al.employee_id = e.id
                WHERE al.window_start >= %s
                AND e.is_active = TRUE
                GROUP BY HOUR(al.window_start)
                ORDER BY hour
            """, [week_ago_utc_start])
            
            hourly_data = cursor.fetchall()
            
            # Define shifts
            shifts = {
                'morning': {'start': 6, 'end': 14, 'data': []},
                'afternoon': {'start': 14, 'end': 22, 'data': []},
                'night': {'start': 22, 'end': 6, 'data': []}
            }
            
            # Categorize by shift
            for hour_data in hourly_data:
                hour = hour_data['hour']
                if 6 <= hour < 14:
                    shifts['morning']['data'].append(hour_data)
                elif 14 <= hour < 22:
                    shifts['afternoon']['data'].append(hour_data)
                else:
                    shifts['night']['data'].append(hour_data)
            
            # Calculate shift metrics
            shift_analysis = {}
            for shift_name, shift_info in shifts.items():
                if shift_info['data']:
                    shift_analysis[shift_name] = {
                        'avg_items_per_hour': round(statistics.mean([float(d['avg_items']) for d in shift_info['data']]), 2),
                        'total_activities': sum(d['activity_count'] for d in shift_info['data']),
                        'avg_active_employees': round(statistics.mean([d['active_employees'] for d in shift_info['data']]), 1),
                        'peak_hour': max(shift_info['data'], key=lambda x: x['avg_items'])['hour']
                    }
                else:
                    shift_analysis[shift_name] = {
                        'avg_items_per_hour': 0,
                        'total_activities': 0,
                        'avg_active_employees': 0,
                        'peak_hour': None
                    }
            
            # Find most productive shift
            most_productive = max(shift_analysis.items(), 
                                key=lambda x: x[1]['avg_items_per_hour'])
            
            return {
                'shifts': shift_analysis,
                'most_productive_shift': most_productive[0],
                'hourly_breakdown': [
                    {
                        'hour': h['hour'],
                        'avg_items': round(float(h['avg_items']), 2),
                        'active_employees': h['active_employees']
                    }
                    for h in hourly_data
                ]
            }
    
    def get_bottlenecks(self) -> List[Dict]:
        """Identify performance bottlenecks and issues"""
        bottlenecks = []
        week_ago = self.tz_helper.get_current_ct_date() - timedelta(days=7)
        week_ago_utc_start, _ = self.tz_helper.ct_date_to_utc_range(week_ago)

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # 1. Check for high idle rates
            cursor.execute("""
                SELECT
                    e.id,
                    e.name,
                    rc.role_name,
                    COUNT(ip.id) as idle_periods_week,
                    COALESCE(SUM(ip.duration_minutes), 0) as total_idle_minutes
                FROM employees e
                JOIN role_configs rc ON e.role_id = rc.id
                LEFT JOIN idle_periods ip ON e.id = ip.employee_id
                    AND ip.start_time >= %s
                WHERE e.is_active = TRUE
                GROUP BY e.id, e.name, rc.role_name
                HAVING idle_periods_week > 10 OR total_idle_minutes > 300
                ORDER BY total_idle_minutes DESC
                LIMIT 5
            """, [week_ago_utc_start])
            
            high_idle_employees = cursor.fetchall()
            if high_idle_employees:
                bottlenecks.append({
                    'type': 'high_idle_rate',
                    'severity': 'high',
                    'description': f"{len(high_idle_employees)} employees with excessive idle time",
                    'affected_employees': [
                        {
                            'name': emp['name'],
                            'role': emp['role_name'],
                            'idle_periods': emp['idle_periods_week'],
                            'total_idle_minutes': int(emp['total_idle_minutes'])
                        }
                        for emp in high_idle_employees
                    ]
                })
            
            # 2. Check for low efficiency teams
            cursor.execute("""
                SELECT
                    rc.role_name,
                    AVG(ds.efficiency_rate) as avg_efficiency,
                    COUNT(DISTINCT e.id) as employee_count
                FROM role_configs rc
                JOIN employees e ON rc.id = e.role_id
                JOIN daily_scores ds ON e.id = ds.employee_id
                WHERE ds.score_date >= %s
                AND e.is_active = TRUE
                GROUP BY rc.id, rc.role_name
                HAVING avg_efficiency < 0.5
            """, [week_ago])
            
            low_efficiency_teams = cursor.fetchall()
            if low_efficiency_teams:
                bottlenecks.append({
                    'type': 'low_team_efficiency',
                    'severity': 'medium',
                    'description': f"{len(low_efficiency_teams)} teams with efficiency below 50%",
                    'affected_teams': [
                        {
                            'role': team['role_name'],
                            'efficiency': round(float(team['avg_efficiency']) * 100, 1),
                            'employee_count': team['employee_count']
                        }
                        for team in low_efficiency_teams
                    ]
                })
            
            # 3. Check for attendance issues
            ct_date = self.tz_helper.get_current_ct_date()
            utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(ct_date)

            cursor.execute("""
                SELECT
                    rc.role_name,
                    COUNT(DISTINCT e.id) as total_employees,
                    COUNT(DISTINCT CASE WHEN ct.clock_in IS NOT NULL THEN e.id END) as present_today,
                    (COUNT(DISTINCT e.id) - COUNT(DISTINCT CASE WHEN ct.clock_in IS NOT NULL THEN e.id END)) as absent_today
                FROM role_configs rc
                JOIN employees e ON rc.id = e.role_id
                LEFT JOIN clock_times ct ON e.id = ct.employee_id
                    AND ct.clock_in >= %s AND ct.clock_in < %s
                WHERE e.is_active = TRUE
                GROUP BY rc.id, rc.role_name
                HAVING absent_today > total_employees * 0.2
            """, [utc_start, utc_end])
            
            attendance_issues = cursor.fetchall()
            if attendance_issues:
                bottlenecks.append({
                    'type': 'attendance_issues',
                    'severity': 'high',
                    'description': f"{len(attendance_issues)} teams with >20% absence rate",
                    'affected_teams': [
                        {
                            'role': team['role_name'],
                            'absent': team['absent_today'],
                            'total': team['total_employees'],
                            'absence_rate': round(team['absent_today'] / team['total_employees'] * 100, 1)
                        }
                        for team in attendance_issues
                    ]
                })
            
            # 4. Check for declining performance
            past_14_days = ct_date - timedelta(days=14)

            cursor.execute("""
                SELECT
                    rc.role_name,
                    AVG(CASE WHEN ds.score_date >= %s
                        THEN ds.points_earned END) as recent_avg,
                    AVG(CASE WHEN ds.score_date < %s
                        AND ds.score_date >= %s
                        THEN ds.points_earned END) as previous_avg
                FROM role_configs rc
                JOIN employees e ON rc.id = e.role_id
                JOIN daily_scores ds ON e.id = ds.employee_id
                WHERE ds.score_date >= %s
                AND e.is_active = TRUE
                GROUP BY rc.id, rc.role_name
                HAVING recent_avg < previous_avg * 0.85
            """, [week_ago, week_ago, past_14_days, past_14_days])
            
            declining_teams = cursor.fetchall()
            if declining_teams:
                bottlenecks.append({
                    'type': 'declining_performance',
                    'severity': 'medium',
                    'description': f"{len(declining_teams)} teams with >15% performance decline",
                    'affected_teams': [
                        {
                            'role': team['role_name'],
                            'recent_avg': round(float(team['recent_avg']), 2),
                            'previous_avg': round(float(team['previous_avg']), 2),
                            'decline_percent': round((1 - float(team['recent_avg']) / float(team['previous_avg'])) * 100, 1)
                        }
                        for team in declining_teams
                    ]
                })
            
            return bottlenecks
    
    def get_capacity_analysis(self) -> Dict:
        """Analyze team capacity and utilization"""
        ct_date = self.tz_helper.get_current_ct_date()

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            # Get capacity by role
            cursor.execute("""
                SELECT
                    rc.id,
                    rc.role_name,
                    rc.expected_per_hour,
                    COUNT(DISTINCT e.id) as employee_count,
                    COUNT(DISTINCT e.id) * rc.expected_per_hour * 8 as theoretical_daily_capacity,
                    COALESCE(SUM(ds.items_processed), 0) as actual_daily_output,
                    COALESCE(AVG(ds.efficiency_rate), 0) as avg_efficiency
                FROM role_configs rc
                LEFT JOIN employees e ON rc.id = e.role_id AND e.is_active = TRUE
                LEFT JOIN daily_scores ds ON e.id = ds.employee_id AND ds.score_date = %s
                GROUP BY rc.id, rc.role_name, rc.expected_per_hour
            """, [ct_date])
            
            capacity_data = []
            total_theoretical = 0
            total_actual = 0
            
            for row in cursor.fetchall():
                theoretical = float(row['theoretical_daily_capacity'])
                actual = float(row['actual_daily_output'])
                utilization = (actual / theoretical * 100) if theoretical > 0 else 0
                
                capacity_data.append({
                    'role_id': row['id'],
                    'role_name': row['role_name'],
                    'employee_count': row['employee_count'],
                    'expected_per_hour': row['expected_per_hour'],
                    'theoretical_daily_capacity': int(theoretical),
                    'actual_daily_output': int(actual),
                    'utilization_percent': round(utilization, 1),
                    'efficiency': round(float(row['avg_efficiency']) * 100, 1)
                })
                
                total_theoretical += theoretical
                total_actual += actual
            
            overall_utilization = (total_actual / total_theoretical * 100) if total_theoretical > 0 else 0
            
            # Identify under/over utilized teams
            underutilized = [t for t in capacity_data if t['utilization_percent'] < 70]
            overutilized = [t for t in capacity_data if t['utilization_percent'] > 90]
            
            return {
                'overall_utilization': round(overall_utilization, 1),
                'total_capacity': int(total_theoretical),
                'total_output': int(total_actual),
                'teams': capacity_data,
                'insights': {
                    'underutilized_teams': underutilized,
                    'overutilized_teams': overutilized,
                    'optimization_potential': int(total_theoretical - total_actual)
                }
            }
