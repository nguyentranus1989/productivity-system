"""Analyze productivity trends and patterns"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import statistics

from database.db_manager import get_db
from models import Employee, DailyScore
from utils.timezone_helpers import TimezoneHelper

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """Analyze productivity trends for employees and teams"""

    def __init__(self):
        self.db = get_db()
        self.tz_helper = TimezoneHelper()
    
    def get_employee_trend(self, employee_id: int, days: int = 30) -> Dict:
        """
        Get productivity trend for an employee
        
        Returns trend data including:
        - Daily points for period
        - Moving averages
        - Trend direction
        - Performance stability
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Get daily scores
        scores = self.db.execute_query(
            """
            SELECT 
                score_date,
                items_processed,
                active_minutes,
                clocked_minutes,
                efficiency_rate,
                points_earned
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date BETWEEN %s AND %s
            ORDER BY score_date
            """,
            (employee_id, start_date, end_date)
        )
        
        if not scores:
            return {
                'employee_id': employee_id,
                'period_days': days,
                'has_data': False
            }
        
        # Calculate trends
        points_data = [float(s['points_earned']) for s in scores]
        efficiency_data = [float(s['efficiency_rate']) for s in scores]
        
        # Calculate moving averages
        ma_7 = self._calculate_moving_average(points_data, 7)
        ma_14 = self._calculate_moving_average(points_data, 14)
        
        # Determine trend direction
        recent_avg = statistics.mean(points_data[-7:]) if len(points_data) >= 7 else statistics.mean(points_data)
        older_avg = statistics.mean(points_data[-14:-7]) if len(points_data) >= 14 else statistics.mean(points_data[:len(points_data)//2])
        
        trend_direction = 'improving' if recent_avg > older_avg * 1.05 else 'declining' if recent_avg < older_avg * 0.95 else 'stable'
        
        # Calculate consistency (coefficient of variation)
        if points_data:
            mean_points = statistics.mean(points_data)
            std_dev = statistics.stdev(points_data) if len(points_data) > 1 else 0
            consistency = 1 - (std_dev / mean_points) if mean_points > 0 else 0
        else:
            consistency = 0
        
        # Find best and worst days
        best_day = max(scores, key=lambda x: x['points_earned'])
        worst_day = min(scores, key=lambda x: x['points_earned'])
        
        return {
            'employee_id': employee_id,
            'period_days': days,
            'has_data': True,
            'total_days_worked': len(scores),
            'trend_direction': trend_direction,
            'consistency_score': round(consistency, 2),
            'average_daily_points': round(statistics.mean(points_data), 2),
            'average_efficiency': round(statistics.mean(efficiency_data) * 100, 1),
            'best_day': {
                'date': best_day['score_date'].isoformat(),
                'points': float(best_day['points_earned']),
                'efficiency': float(best_day['efficiency_rate']) * 100
            },
            'worst_day': {
                'date': worst_day['score_date'].isoformat(),
                'points': float(worst_day['points_earned']),
                'efficiency': float(worst_day['efficiency_rate']) * 100
            },
            'daily_points': [
                {
                    'date': s['score_date'].isoformat(),
                    'points': float(s['points_earned'])
                }
                for s in scores
            ],
            'moving_averages': {
                '7_day': ma_7,
                '14_day': ma_14
            }
        }
    
    def get_team_trend(self, role_id: Optional[int] = None, days: int = 30) -> Dict:
        """Get productivity trend for a team or role"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Build query
        where_clause = "WHERE ds.score_date BETWEEN %s AND %s"
        params = [start_date, end_date]
        
        if role_id:
            where_clause += " AND e.role_id = %s"
            params.append(role_id)
        
        # Get aggregated daily data
        daily_stats = self.db.execute_query(
            f"""
            SELECT 
                ds.score_date,
                COUNT(DISTINCT ds.employee_id) as active_employees,
                SUM(ds.items_processed) as total_items,
                SUM(ds.points_earned) as total_points,
                AVG(ds.efficiency_rate) as avg_efficiency,
                MIN(ds.efficiency_rate) as min_efficiency,
                MAX(ds.efficiency_rate) as max_efficiency
            FROM daily_scores ds
            JOIN employees e ON ds.employee_id = e.id
            {where_clause}
            GROUP BY ds.score_date
            ORDER BY ds.score_date
            """,
            params
        )
        
        if not daily_stats:
            return {
                'role_id': role_id,
                'period_days': days,
                'has_data': False
            }
        
        # Calculate team trends
        total_points_by_day = [float(d['total_points']) for d in daily_stats]
        avg_efficiency_by_day = [float(d['avg_efficiency']) for d in daily_stats]
        
        # Trend direction
        recent_points = statistics.mean(total_points_by_day[-7:]) if len(total_points_by_day) >= 7 else statistics.mean(total_points_by_day)
        older_points = statistics.mean(total_points_by_day[-14:-7]) if len(total_points_by_day) >= 14 else statistics.mean(total_points_by_day[:len(total_points_by_day)//2])
        
        trend_direction = 'improving' if recent_points > older_points * 1.05 else 'declining' if recent_points < older_points * 0.95 else 'stable'
        
        # Top performers
        top_performers = self.db.execute_query(
            f"""
            SELECT 
                e.id,
                e.name,
                e.email,
                AVG(ds.points_earned) as avg_points,
                AVG(ds.efficiency_rate) as avg_efficiency,
                COUNT(ds.id) as days_worked
            FROM daily_scores ds
            JOIN employees e ON ds.employee_id = e.id
            {where_clause}
            GROUP BY e.id, e.name, e.email
            HAVING days_worked >= 5
            ORDER BY avg_points DESC
            LIMIT 5
            """,
            params
        )
        
        return {
            'role_id': role_id,
            'period_days': days,
            'has_data': True,
            'trend_direction': trend_direction,
            'average_daily_points': round(statistics.mean(total_points_by_day), 2),
            'average_efficiency': round(statistics.mean(avg_efficiency_by_day) * 100, 1),
            'total_points': round(sum(total_points_by_day), 2),
            'daily_stats': [
                {
                    'date': d['score_date'].isoformat(),
                    'active_employees': d['active_employees'],
                    'total_points': float(d['total_points']),
                    'avg_efficiency': float(d['avg_efficiency']) * 100
                }
                for d in daily_stats
            ],
            'top_performers': [
                {
                    'employee_id': p['id'],
                    'name': p['name'],
                    'avg_points': round(float(p['avg_points']), 2),
                    'avg_efficiency': round(float(p['avg_efficiency']) * 100, 1),
                    'days_worked': p['days_worked']
                }
                for p in top_performers
            ]
        }
    
    def predict_monthly_performance(self, employee_id: int) -> Dict:
        """Predict if employee will meet monthly target"""
        # Get current month data
        today = date.today()
        month_start = date(today.year, today.month, 1)
        days_in_month = 30  # Simplified
        days_elapsed = (today - month_start).days + 1
        days_remaining = days_in_month - days_elapsed
        
        # Get employee's role and target
        employee_info = self.db.execute_one(
            """
            SELECT 
                e.name,
                rc.monthly_target,
                rc.role_name
            FROM employees e
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE e.id = %s
            """,
            (employee_id,)
        )
        
        if not employee_info:
            return {'error': 'Employee not found'}
        
        # Get current month performance
        current_month_data = self.db.execute_one(
            """
            SELECT 
                SUM(points_earned) as current_points,
                COUNT(*) as days_worked,
                AVG(points_earned) as avg_daily_points
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date >= %s
            """,
            (employee_id, month_start)
        )
        
        current_points = float(current_month_data['current_points'] or 0)
        avg_daily_points = float(current_month_data['avg_daily_points'] or 0)
        
        # Get recent trend (last 7 days)
        recent_trend = self.db.execute_one(
            """
            SELECT AVG(points_earned) as recent_avg
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date >= %s
            """,
            (employee_id, today - timedelta(days=7))
        )
        
        recent_avg = float(recent_trend['recent_avg'] or avg_daily_points)
        
        # Predict end of month
        # Use weighted average (recent performance weighs more)
        predicted_daily = (recent_avg * 0.7) + (avg_daily_points * 0.3)
        predicted_remaining = predicted_daily * days_remaining
        predicted_total = current_points + predicted_remaining
        
        # Calculate probability of meeting target
        target = float(employee_info['monthly_target'])
        progress_percent = (current_points / target * 100) if target > 0 else 0
        predicted_percent = (predicted_total / target * 100) if target > 0 else 0
        
        # Simple probability based on current trajectory
        if predicted_percent >= 100:
            probability = min(0.9, predicted_percent / 100)
        else:
            probability = predicted_percent / 100 * 0.8  # Slightly pessimistic
        
        return {
            'employee_id': employee_id,
            'employee_name': employee_info['name'],
            'role': employee_info['role_name'],
            'month': today.strftime('%Y-%m'),
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'monthly_target': target,
            'current_points': round(current_points, 2),
            'progress_percent': round(progress_percent, 1),
            'predicted_total': round(predicted_total, 2),
            'predicted_percent': round(predicted_percent, 1),
            'probability_of_meeting_target': round(probability, 2),
            'daily_average_needed': round((target - current_points) / days_remaining, 2) if days_remaining > 0 else 0,
            'current_daily_average': round(avg_daily_points, 2),
            'recent_daily_average': round(recent_avg, 2),
            'status': 'on_track' if predicted_percent >= 100 else 'at_risk' if predicted_percent >= 80 else 'behind'
        }
    
    def _calculate_moving_average(self, data: List[float], window: int) -> List[float]:
        """Calculate moving average"""
        if len(data) < window:
            return [statistics.mean(data)] * len(data)
        
        ma = []
        for i in range(len(data)):
            if i < window - 1:
                # Not enough data points yet
                ma.append(statistics.mean(data[:i+1]))
            else:
                # Calculate moving average
                ma.append(statistics.mean(data[i-window+1:i+1]))
        
        return ma
    
    def identify_performance_patterns(self, employee_id: int) -> Dict:
        """Identify patterns in employee performance"""
        # Get last 60 days of data
        scores = self.db.execute_query(
            """
            SELECT
                score_date,
                DAYNAME(score_date) as day_name,
                DAYOFWEEK(score_date) as day_of_week,
                WEEK(score_date) as week_num,
                points_earned,
                efficiency_rate,
                items_processed
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date >= %s
            ORDER BY score_date
            """,
            (employee_id, self.tz_helper.get_current_ct_date() - timedelta(days=60))
        )
        
        if not scores:
            return {'employee_id': employee_id, 'patterns': []}
        
        patterns = []
        
        # Day of week analysis
        by_day = defaultdict(list)
        for score in scores:
            by_day[score['day_name']].append(float(score['points_earned']))
        
        day_averages = {day: statistics.mean(points) for day, points in by_day.items() if points}
        if day_averages:
            best_day = max(day_averages.items(), key=lambda x: x[1])
            worst_day = min(day_averages.items(), key=lambda x: x[1])
            
            if best_day[1] > worst_day[1] * 1.2:  # 20% difference
                patterns.append({
                    'type': 'day_of_week',
                    'finding': f"Performs best on {best_day[0]}s ({best_day[1]:.1f} points) and worst on {worst_day[0]}s ({worst_day[1]:.1f} points)",
                    'significance': 'high' if best_day[1] > worst_day[1] * 1.5 else 'medium'
                })
        
        # Weekly trend within month
        by_week = defaultdict(list)
        for score in scores:
            week_in_month = ((score['score_date'].day - 1) // 7) + 1
            by_week[week_in_month].append(float(score['points_earned']))
        
        week_averages = {week: statistics.mean(points) for week, points in by_week.items() if points}
        if len(week_averages) >= 3:
            if week_averages.get(1, 0) > week_averages.get(4, week_averages.get(3, 0)) * 1.15:
                patterns.append({
                    'type': 'monthly_cycle',
                    'finding': "Performance tends to be higher at the beginning of the month",
                    'significance': 'medium'
                })
        
        # Consistency analysis
        all_points = [float(s['points_earned']) for s in scores]
        if len(all_points) > 1:
            cv = statistics.stdev(all_points) / statistics.mean(all_points)
            if cv < 0.15:
                patterns.append({
                    'type': 'consistency',
                    'finding': "Very consistent performance (low variation)",
                    'significance': 'high'
                })
            elif cv > 0.5:
                patterns.append({
                    'type': 'consistency',
                    'finding': "Highly variable performance",
                    'significance': 'medium'
                })
        
        return {
            'employee_id': employee_id,
            'analysis_period': '60 days',
            'patterns': patterns,
            'performance_summary': {
                'average_points': round(statistics.mean(all_points), 2) if all_points else 0,
                'best_day_type': best_day[0] if day_averages else None,
                'consistency_score': round(1 - cv, 2) if len(all_points) > 1 else 0
            }
        }
