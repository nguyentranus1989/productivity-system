"""Predictive scoring and recommendations"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import statistics
from collections import defaultdict

from database.db_manager import get_db
from calculations.trend_analyzer import TrendAnalyzer

logger = logging.getLogger(__name__)

class PredictiveScorer:
    """Generate predictive scores and recommendations"""
    
    def __init__(self):
        self.db = get_db()
        self.trend_analyzer = TrendAnalyzer()
    
    def calculate_performance_score(self, employee_id: int) -> Dict:
        """
        Calculate comprehensive performance score (0-100)
        
        Components:
        - Current productivity (40%)
        - Trend/improvement (20%)
        - Consistency (20%)
        - Attendance (10%)
        - Efficiency (10%)
        """
        # Get last 30 days data
        end_date = date.today()
        start_date = end_date - timedelta(days=29)
        
        scores = self.db.execute_query(
            """
            SELECT 
                ds.*,
                rc.monthly_target,
                rc.expected_per_hour
            FROM daily_scores ds
            JOIN employees e ON ds.employee_id = e.id
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE ds.employee_id = %s
            AND ds.score_date BETWEEN %s AND %s
            """,
            (employee_id, start_date, end_date)
        )
        
        if not scores:
            return {
                'employee_id': employee_id,
                'performance_score': 0,
                'components': {},
                'has_data': False
            }
        
        # 1. Current Productivity Score (40%)
        daily_target = scores[0]['monthly_target'] / 30  # Simplified
        recent_points = [s['points_earned'] for s in scores[-7:]]  # Last 7 days
        avg_recent = statistics.mean(recent_points) if recent_points else 0
        productivity_score = min(100, (avg_recent / daily_target) * 100) * 0.4
        
        # 2. Trend Score (20%)
        if len(scores) >= 14:
            first_week_avg = statistics.mean([s['points_earned'] for s in scores[:7]])
            last_week_avg = statistics.mean([s['points_earned'] for s in scores[-7:]])
            if first_week_avg > 0:
                improvement_ratio = last_week_avg / first_week_avg
                trend_score = min(100, improvement_ratio * 50) * 0.2
            else:
                trend_score = 10  # Default if no baseline
        else:
            trend_score = 10  # Not enough data
        
        # 3. Consistency Score (20%)
        all_points = [s['points_earned'] for s in scores]
        if len(all_points) > 1:
            cv = statistics.stdev(all_points) / statistics.mean(all_points)
            consistency_score = max(0, (1 - cv)) * 100 * 0.2
        else:
            consistency_score = 10
        
        # 4. Attendance Score (10%)
        expected_days = (end_date - start_date).days + 1
        weekdays = sum(1 for d in range(expected_days) 
                      if (start_date + timedelta(days=d)).weekday() < 5)
        attendance_rate = len(scores) / weekdays
        attendance_score = min(100, attendance_rate * 100) * 0.1
        
        # 5. Efficiency Score (10%)
        avg_efficiency = statistics.mean([s['efficiency_rate'] for s in scores])
        efficiency_score = avg_efficiency * 100 * 0.1
        
        # Total score
        total_score = (
            productivity_score + 
            trend_score + 
            consistency_score + 
            attendance_score + 
            efficiency_score
        )
        
        return {
            'employee_id': employee_id,
            'performance_score': round(total_score, 1),
            'components': {
                'productivity': round(productivity_score / 0.4, 1),
                'trend': round(trend_score / 0.2, 1),
                'consistency': round(consistency_score / 0.2, 1),
                'attendance': round(attendance_score / 0.1, 1),
                'efficiency': round(efficiency_score / 0.1, 1)
            },
            'rating': self._get_rating(total_score),
            'has_data': True
        }
    
    def generate_recommendations(self, employee_id: int) -> List[Dict]:
        """Generate personalized recommendations"""
        recommendations = []
        
        # Get performance score components
        perf_score = self.calculate_performance_score(employee_id)
        if not perf_score.get('has_data'):
            return []
        
        components = perf_score['components']
        
        # Get additional data
        patterns = self.trend_analyzer.identify_performance_patterns(employee_id)
        prediction = self.trend_analyzer.predict_monthly_performance(employee_id)
        
        # 1. Productivity recommendations
        if components['productivity'] < 70:
            recommendations.append({
                'category': 'productivity',
                'priority': 'high',
                'recommendation': 'Focus on increasing daily output',
                'specific_action': f"Aim for {prediction['daily_average_needed']:.0f} points per day to meet monthly target",
                'impact': 'high'
            })
        
        # 2. Consistency recommendations
        if components['consistency'] < 60:
            recommendations.append({
                'category': 'consistency',
                'priority': 'medium',
                'recommendation': 'Work on maintaining steady performance',
                'specific_action': 'Avoid large variations in daily output. Set daily goals.',
                'impact': 'medium'
            })
        
        # 3. Trend recommendations
        if components['trend'] < 50:
            recommendations.append({
                'category': 'improvement',
                'priority': 'high',
                'recommendation': 'Performance is declining',
                'specific_action': 'Review work methods and seek support if needed',
                'impact': 'high'
            })
        elif components['trend'] > 80:
            recommendations.append({
                'category': 'improvement',
                'priority': 'low',
                'recommendation': 'Great improvement! Keep it up!',
                'specific_action': 'Continue current practices',
                'impact': 'positive'
            })
        
        # 4. Pattern-based recommendations
        for pattern in patterns.get('patterns', []):
            if pattern['type'] == 'day_of_week' and pattern['significance'] == 'high':
                recommendations.append({
                    'category': 'scheduling',
                    'priority': 'medium',
                    'recommendation': pattern['finding'],
                    'specific_action': 'Consider workload distribution across the week',
                    'impact': 'medium'
                })
        
        # 5. Target achievement recommendations
        if prediction.get('status') == 'at_risk':
            recommendations.append({
                'category': 'monthly_target',
                'priority': 'high',
                'recommendation': f"At risk of missing monthly target ({prediction['predicted_percent']:.1f}% predicted)",
                'specific_action': f"Increase daily average from {prediction['current_daily_average']:.1f} to {prediction['daily_average_needed']:.1f} points",
                'impact': 'high'
            })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return recommendations[:5]  # Top 5 recommendations
    
    def predict_end_of_day_score(self, employee_id: int) -> Dict:
        """Predict end of day performance based on current progress"""
        today = date.today()
        now = datetime.now()
        
        # Get today's activities so far
        today_data = self.db.execute_one(
            """
            SELECT 
                COUNT(*) as activity_count,
                SUM(items_count) as items_so_far,
                MIN(window_start) as first_activity,
                MAX(window_end) as last_activity
            FROM activity_logs
            WHERE employee_id = %s
            AND DATE(window_start) = %s
            """,
            (employee_id, today)
        )
        
        if not today_data or not today_data['activity_count']:
            return {
                'employee_id': employee_id,
                'has_activity': False,
                'predicted_points': 0
            }
        
        # Get clock in time
        clock_data = self.db.execute_one(
            """
            SELECT clock_in, clock_out
            FROM clock_times
            WHERE employee_id = %s
            AND DATE(clock_in) = %s
            """,
            (employee_id, today)
        )
        
        if not clock_data:
            return {
                'employee_id': employee_id,
                'has_activity': True,
                'has_clock': False,
                'items_so_far': today_data['items_so_far']
            }
        
        # Calculate progress
        clock_in = clock_data['clock_in']
        planned_clock_out = clock_data['clock_out'] or clock_in.replace(hour=17, minute=0)
        
        total_work_minutes = (planned_clock_out - clock_in).total_seconds() / 60
        elapsed_minutes = (now - clock_in).total_seconds() / 60
        progress_percent = elapsed_minutes / total_work_minutes
        
        # Get employee's typical pattern
        hourly_pattern = self.db.execute_query(
            """
            SELECT 
                HOUR(window_start) as hour,
                AVG(items_count) as avg_items
            FROM activity_logs
            WHERE employee_id = %s
            AND window_start >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY HOUR(window_start)
            """,
            (employee_id,)
        )
        
        # Simple prediction
        items_so_far = today_data['items_so_far'] or 0
        if progress_percent > 0:
            simple_prediction = items_so_far / progress_percent
        else:
            simple_prediction = 0
        
        # Get role multiplier and calculate points
        role_data = self.db.execute_one(
            """
            SELECT rc.multiplier, rc.role_type
            FROM employees e
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE e.id = %s
            """,
            (employee_id,)
        )
        
        # Assume 80% efficiency for prediction
        predicted_efficiency = 0.8
        predicted_points = simple_prediction * role_data['multiplier'] * predicted_efficiency
        
        return {
            'employee_id': employee_id,
            'has_activity': True,
            'has_clock': True,
            'current_time': now.isoformat(),
            'items_so_far': items_so_far,
            'work_progress_percent': round(progress_percent * 100, 1),
            'predicted_total_items': round(simple_prediction),
            'predicted_points': round(predicted_points, 2),
            'on_track': predicted_points >= (today_data.get('daily_target', 50) * 0.9)
        }
    
    def _get_rating(self, score: float) -> str:
        """Convert numeric score to rating"""
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 60:
            return 'satisfactory'
        elif score >= 40:
            return 'needs_improvement'
        else:
            return 'poor'
    
    def get_team_predictions(self, role_id: Optional[int] = None) -> Dict:
        """Get predictions for entire team"""
        where_clause = "WHERE e.is_active = TRUE"
        params = []
        
        if role_id:
            where_clause += " AND e.role_id = %s"
            params.append(role_id)
        
        employees = self.db.execute_query(
            f"""
            SELECT e.id, e.name, rc.role_name
            FROM employees e
            JOIN role_configs rc ON e.role_id = rc.id
            {where_clause}
            """,
            params
        )
        
        predictions = []
        at_risk_count = 0
        on_track_count = 0
        
        for emp in employees:
            # Get monthly prediction
            monthly = self.trend_analyzer.predict_monthly_performance(emp['id'])
            
            # Get performance score
            perf_score = self.calculate_performance_score(emp['id'])
            
            if monthly.get('status') == 'at_risk':
                at_risk_count += 1
            elif monthly.get('status') == 'on_track':
                on_track_count += 1
            
            predictions.append({
                'employee_id': emp['id'],
                'name': emp['name'],
                'role': emp['role_name'],
                'performance_score': perf_score.get('performance_score', 0),
                'monthly_prediction': monthly.get('predicted_percent', 0),
                'status': monthly.get('status', 'unknown')
            })
        
        # Sort by risk (at_risk first, then by performance score)
        predictions.sort(key=lambda x: (
            0 if x['status'] == 'at_risk' else 1,
            x['performance_score']
        ))
        
        return {
            'role_id': role_id,
            'total_employees': len(employees),
            'at_risk': at_risk_count,
            'on_track': on_track_count,
            'employees': predictions,
            'summary': {
                'risk_percentage': round(at_risk_count / len(employees) * 100, 1) if employees else 0,
                'average_performance_score': round(
                    statistics.mean([p['performance_score'] for p in predictions if p['performance_score'] > 0]),
                    1
                ) if predictions else 0
            }
        }
