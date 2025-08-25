"""Predict future performance using historical patterns"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import statistics
from collections import defaultdict

from database.db_manager import get_db

logger = logging.getLogger(__name__)

class PerformancePredictor:
    """Predict employee performance using historical data patterns"""
    
    def __init__(self):
        self.db = get_db()
    
    def predict_next_day_performance(self, employee_id: int) -> Dict:
        """
        Predict next day's performance based on:
        - Historical average for that day of week
        - Recent trend (last 7 days)
        - Seasonal factors
        - Personal patterns
        """
        tomorrow = date.today() + timedelta(days=1)
        day_name = tomorrow.strftime('%A')
        
        # Get historical performance for this day of week
        historical_data = self.db.execute_query(
            """
            SELECT 
                AVG(points_earned) as avg_points,
                AVG(efficiency_rate) as avg_efficiency,
                AVG(items_processed) as avg_items,
                COUNT(*) as sample_size
            FROM daily_scores
            WHERE employee_id = %s
            AND DAYNAME(score_date) = %s
            AND score_date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
            """,
            (employee_id, day_name)
        )
        
        if not historical_data or not historical_data[0]['sample_size']:
            return {
                'employee_id': employee_id,
                'prediction_date': tomorrow.isoformat(),
                'has_data': False,
                'message': f'No historical data for {day_name}s'
            }
        
        hist_data = historical_data[0]
        
        # Get recent trend (last 7 days)
        recent_data = self.db.execute_query(
            """
            SELECT 
                score_date,
                points_earned,
                efficiency_rate,
                items_processed
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ORDER BY score_date DESC
            """,
            (employee_id,)
        )
        
        if recent_data:
            recent_points = [float(d['points_earned']) for d in recent_data]
            recent_avg = statistics.mean(recent_points)
            
            # Calculate trend factor
            if len(recent_points) >= 3:
                first_half = statistics.mean(recent_points[len(recent_points)//2:])
                second_half = statistics.mean(recent_points[:len(recent_points)//2])
                trend_factor = second_half / first_half if first_half > 0 else 1
            else:
                trend_factor = 1
        else:
            recent_avg = float(hist_data['avg_points'])
            trend_factor = 1
        
        # Combine historical and recent data with weights
        base_prediction = (float(hist_data['avg_points']) * 0.4) + (recent_avg * 0.6)
        
        # Apply trend factor
        adjusted_prediction = base_prediction * trend_factor
        
        # Get confidence level based on data availability
        confidence = self._calculate_confidence(hist_data['sample_size'], len(recent_data))
        
        # Calculate range (± based on historical variance)
        variance_data = self.db.execute_one(
            """
            SELECT STDDEV(points_earned) as std_dev
            FROM daily_scores
            WHERE employee_id = %s
            AND DAYNAME(score_date) = %s
            AND score_date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
            """,
            (employee_id, day_name)
        )
        
        std_dev = float(variance_data['std_dev'] or 0)
        
        return {
            'employee_id': employee_id,
            'prediction_date': tomorrow.isoformat(),
            'day_of_week': day_name,
            'has_data': True,
            'predicted_points': round(adjusted_prediction, 2),
            'predicted_range': {
                'low': round(max(0, adjusted_prediction - std_dev), 2),
                'high': round(adjusted_prediction + std_dev, 2)
            },
            'predicted_efficiency': round(float(hist_data['avg_efficiency']) * 100, 1),
            'predicted_items': round(float(hist_data['avg_items'])),
            'confidence_level': confidence,
            'factors': {
                'historical_average': round(float(hist_data['avg_points']), 2),
                'recent_average': round(recent_avg, 2),
                'trend_factor': round(trend_factor, 2),
                'sample_size': hist_data['sample_size']
            }
        }
    
    def predict_week_performance(self, employee_id: int) -> Dict:
        """Predict performance for the next 7 days"""
        predictions = []
        weekly_total = 0
        
        for days_ahead in range(1, 8):
            future_date = date.today() + timedelta(days=days_ahead)
            day_name = future_date.strftime('%A')
            
            # Skip weekends if employee doesn't usually work weekends
            weekend_check = self.db.execute_one(
                """
                SELECT COUNT(*) as weekend_days
                FROM daily_scores
                WHERE employee_id = %s
                AND DAYOFWEEK(score_date) IN (1, 7)
                AND score_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                """,
                (employee_id,)
            )
            
            if day_name in ['Saturday', 'Sunday'] and weekend_check['weekend_days'] == 0:
                predictions.append({
                    'date': future_date.isoformat(),
                    'day': day_name,
                    'predicted_points': 0,
                    'is_working_day': False
                })
                continue
            
            # Get prediction for this day
            day_prediction = self._predict_specific_day(employee_id, future_date, day_name)
            
            predictions.append({
                'date': future_date.isoformat(),
                'day': day_name,
                'predicted_points': day_prediction['points'],
                'confidence': day_prediction['confidence'],
                'is_working_day': True
            })
            
            weekly_total += day_prediction['points']
        
        # Get employee's role target
        role_info = self.db.execute_one(
            """
            SELECT rc.monthly_target, rc.role_name
            FROM employees e
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE e.id = %s
            """,
            (employee_id,)
        )
        
        weekly_target = float(role_info['monthly_target']) / 4 if role_info else 0
        
        return {
            'employee_id': employee_id,
            'week_starting': (date.today() + timedelta(days=1)).isoformat(),
            'predictions': predictions,
            'predicted_weekly_total': round(weekly_total, 2),
            'weekly_target': round(weekly_target, 2),
            'on_track': weekly_total >= weekly_target * 0.95,
            'role': role_info['role_name'] if role_info else None
        }
    
    def identify_risk_factors(self, employee_id: int) -> List[Dict]:
        """Identify factors that might impact future performance"""
        risk_factors = []
        
        # 1. Declining trend
        trend_data = self.db.execute_query(
            """
            SELECT 
                AVG(CASE WHEN score_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) 
                    THEN points_earned END) as recent_avg,
                AVG(CASE WHEN score_date < DATE_SUB(CURDATE(), INTERVAL 7 DAY) 
                    AND score_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
                    THEN points_earned END) as previous_avg
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            """,
            (employee_id,)
        )
        
        if trend_data and trend_data[0]['recent_avg'] and trend_data[0]['previous_avg']:
            recent = float(trend_data[0]['recent_avg'])
            previous = float(trend_data[0]['previous_avg'])
            
            if recent < previous * 0.85:  # 15% decline
                risk_factors.append({
                    'type': 'declining_trend',
                    'severity': 'high',
                    'description': f'Performance declined {round((1 - recent/previous) * 100, 1)}% in last week',
                    'impact': 'May continue to underperform'
                })
        
        # 2. High idle time recently
        idle_data = self.db.execute_one(
            """
            SELECT 
                COUNT(*) as idle_periods,
                SUM(duration_minutes) as total_idle
            FROM idle_periods
            WHERE employee_id = %s
            AND start_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """,
            (employee_id,)
        )
        
        if idle_data and idle_data['idle_periods'] > 10:
            risk_factors.append({
                'type': 'high_idle_time',
                'severity': 'medium',
                'description': f'{idle_data["idle_periods"]} idle periods in last 7 days',
                'impact': 'Efficiency likely to remain low'
            })
        
        # 3. Inconsistent attendance
        attendance_data = self.db.execute_one(
            """
            SELECT 
                COUNT(DISTINCT DATE(clock_in)) as days_worked,
                DATEDIFF(CURDATE(), DATE_SUB(CURDATE(), INTERVAL 14 DAY)) as expected_days
            FROM clock_times
            WHERE employee_id = %s
            AND clock_in >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            """,
            (employee_id,)
        )
        
        if attendance_data:
            attendance_rate = attendance_data['days_worked'] / 10  # Assume 5-day work week
            if attendance_rate < 0.8:
                risk_factors.append({
                    'type': 'attendance_issues',
                    'severity': 'high',
                    'description': f'Only worked {attendance_data["days_worked"]} days in last 2 weeks',
                    'impact': 'May miss more days affecting monthly target'
                })
        
        # 4. Below target trajectory
        current_month = self.db.execute_one(
            """
            SELECT 
                SUM(points_earned) as current_points,
                DAY(CURDATE()) as days_elapsed
            FROM daily_scores
            WHERE employee_id = %s
            AND MONTH(score_date) = MONTH(CURDATE())
            AND YEAR(score_date) = YEAR(CURDATE())
            """,
            (employee_id,)
        )
        
        if current_month and current_month['current_points']:
            # Get monthly target
            target_data = self.db.execute_one(
                """
                SELECT rc.monthly_target
                FROM employees e
                JOIN role_configs rc ON e.role_id = rc.id
                WHERE e.id = %s
                """,
                (employee_id,)
            )
            
            if target_data:
                expected_progress = (current_month['days_elapsed'] / 30) * float(target_data['monthly_target'])
                actual_progress = float(current_month['current_points'])
                
                if actual_progress < expected_progress * 0.8:
                    risk_factors.append({
                        'type': 'behind_target',
                        'severity': 'medium',
                        'description': f'Only at {round(actual_progress/expected_progress*100, 1)}% of expected progress',
                        'impact': 'Unlikely to meet monthly target without improvement'
                    })
        
        return risk_factors
    
    def _predict_specific_day(self, employee_id: int, target_date: date, day_name: str) -> Dict:
        """Helper to predict performance for a specific day"""
        # Get historical average for this day of week
        hist_data = self.db.execute_one(
            """
            SELECT 
                AVG(points_earned) as avg_points,
                COUNT(*) as sample_size
            FROM daily_scores
            WHERE employee_id = %s
            AND DAYNAME(score_date) = %s
            AND score_date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
            """,
            (employee_id, day_name)
        )
        
        if not hist_data or not hist_data['sample_size']:
            # No data for this day, use overall average
            overall = self.db.execute_one(
                """
                SELECT AVG(points_earned) as avg_points
                FROM daily_scores
                WHERE employee_id = %s
                AND score_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                """,
                (employee_id,)
            )
            
            return {
                'points': float(overall['avg_points'] or 0),
                'confidence': 'low'
            }
        
        points = float(hist_data['avg_points'])
        confidence = 'high' if hist_data['sample_size'] >= 4 else 'medium' if hist_data['sample_size'] >= 2 else 'low'
        
        return {
            'points': round(points, 2),
            'confidence': confidence
        }
    
    def _calculate_confidence(self, historical_samples: int, recent_samples: int) -> str:
        """Calculate confidence level for prediction"""
        total_samples = historical_samples + recent_samples
        
        if total_samples >= 20:
            return 'high'
        elif total_samples >= 10:
            return 'medium'
        else:
            return 'low'
