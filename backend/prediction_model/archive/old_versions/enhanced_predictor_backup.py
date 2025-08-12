#!/usr/bin/env python3
"""
Enhanced Warehouse Prediction Model v3
Includes holidays, QC constraints, weather, and customer patterns
"""

from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import logging
import json

class EnhancedWarehousePredictor:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.base_average = 0
        self.patterns = {
            'day_of_week': {},
            'week_of_month': {},
            'month': {},
            'trends': {},
            'special_events': {},
            'customer_patterns': {},
            'holidays': {}
        }
        self.accuracy_history = []
        self.qc_capacity = self.calculate_qc_capacity()
        
    def calculate_qc_capacity(self):
        """Determine actual QC capacity from historical data"""
        cursor = self.conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                DATE(window_start) as date,
                SUM(items_count) as daily_qc
            FROM activity_logs
            WHERE activity_type IN ('QC Passed', 'QC/Outbound')
            AND DATE(window_start) >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY DATE(window_start)
            ORDER BY daily_qc DESC
            LIMIT 5
        """)
        
        top_days = cursor.fetchall()
        if top_days:
            # 95th percentile capacity
            max_capacity = np.mean([d['daily_qc'] for d in top_days])
            practical_capacity = max_capacity * 0.95  # 95% of max
        else:
            practical_capacity = 2000  # Default fallback
            
        cursor.close()
        print(f"📦 QC Capacity calculated: {practical_capacity:.0f} items/day")
        return practical_capacity
    
    def detect_holidays(self, target_date):
        """Comprehensive holiday detection with impact"""
        
        # US Federal Holidays and retail events
        holidays_2025 = {
            '2025-01-01': {'name': 'New Year', 'impact': 0.3},  # 70% reduction
            '2025-01-20': {'name': 'MLK Day', 'impact': 0.8},
            '2025-02-14': {'name': 'Valentine\'s Day', 'impact': 1.2},  # 20% increase
            '2025-02-17': {'name': 'Presidents Day', 'impact': 0.8},
            '2025-05-26': {'name': 'Memorial Day', 'impact': 0.5},
            '2025-07-04': {'name': 'Independence Day', 'impact': 0.4},
            '2025-09-01': {'name': 'Labor Day', 'impact': 0.6},
            '2025-10-13': {'name': 'Columbus Day', 'impact': 0.9},
            '2025-11-11': {'name': 'Veterans Day', 'impact': 0.9},
            '2025-11-27': {'name': 'Thanksgiving', 'impact': 0.2},
            '2025-11-28': {'name': 'Black Friday', 'impact': 1.8},  # 80% increase
            '2025-12-01': {'name': 'Cyber Monday', 'impact': 1.6},
            '2025-12-24': {'name': 'Christmas Eve', 'impact': 0.5},
            '2025-12-25': {'name': 'Christmas', 'impact': 0.1},
            '2025-12-31': {'name': 'New Year\'s Eve', 'impact': 0.6}
        }
        
        date_str = target_date.strftime('%Y-%m-%d')
        
        # Direct holiday
        if date_str in holidays_2025:
            holiday = holidays_2025[date_str]
            return {
                'is_holiday': True,
                'name': holiday['name'],
                'multiplier': holiday['impact'],
                'type': 'direct'
            }
        
        # Day after holiday (catch-up effect)
        yesterday = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
        if yesterday in holidays_2025:
            holiday = holidays_2025[yesterday]
            if holiday['impact'] < 0.5:  # Major holiday
                return {
                    'is_holiday': False,
                    'name': f"Day after {holiday['name']}",
                    'multiplier': 1.4,  # 40% boost
                    'type': 'day_after'
                }
        
        # Week before major holidays
        for days_ahead in range(1, 8):
            future_date = (target_date + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            if future_date in holidays_2025:
                holiday = holidays_2025[future_date]
                if holiday['name'] in ['Christmas', 'Thanksgiving']:
                    return {
                        'is_holiday': False,
                        'name': f"Week before {holiday['name']}",
                        'multiplier': 1.15,  # 15% boost
                        'type': 'pre_holiday'
                    }
        
        return {
            'is_holiday': False,
            'name': None,
            'multiplier': 1.0,
            'type': 'regular'
        }
    
    def apply_qc_constraint(self, prediction, date):
        """Apply realistic QC capacity constraints"""
        
        # Check if QC is running that day
        day_name = date.strftime('%A')
        
        # Reduced capacity on weekends
        if day_name == 'Saturday':
            qc_capacity = self.qc_capacity * 0.8
        elif day_name == 'Sunday':
            qc_capacity = self.qc_capacity * 0.6
        else:
            qc_capacity = self.qc_capacity
        
        if prediction > qc_capacity:
            return {
                'original_prediction': prediction,
                'constrained_prediction': int(qc_capacity),
                'overflow': int(prediction - qc_capacity),
                'constraint_applied': True,
                'reason': f'QC capacity limit ({qc_capacity:.0f} items/day)',
                'suggestion': 'Consider scheduling overtime or additional QC staff'
            }
        
        return {
            'original_prediction': prediction,
            'constrained_prediction': prediction,
            'overflow': 0,
            'constraint_applied': False,
            'reason': None
        }
    
    def detect_customer_patterns(self, target_date):
        """Detect recurring customer order patterns"""
        
        cursor = self.conn.cursor(dictionary=True)
        
        # Check for patterns on this day of month
        day_of_month = target_date.day
        day_name = target_date.strftime('%A')
        
        # First Monday pattern (already detected in training)
        if day_of_month <= 7 and day_name == 'Monday':
            return {'multiplier': 1.15, 'pattern': 'First Monday of month'}
        
        # Month-end pattern (25th-31st)
        if day_of_month >= 25:
            return {'multiplier': 0.95, 'pattern': 'Month-end'}
        
        # Check historical patterns for specific date patterns
        cursor.execute("""
            SELECT 
                DAY(prediction_date) as day,
                AVG(actual_orders) as avg_orders
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND DAY(prediction_date) = %s
            GROUP BY DAY(prediction_date)
            HAVING COUNT(*) >= 3
        """, (day_of_month,))
        
        result = cursor.fetchone()
        if result and self.base_average > 0:
            multiplier = float(result['avg_orders']) / self.base_average
            if multiplier > 1.2 or multiplier < 0.8:  # Significant pattern
                return {
                    'multiplier': multiplier,
                    'pattern': f'Day {day_of_month} pattern'
                }
        
        cursor.close()
        return {'multiplier': 1.0, 'pattern': None}
    
    def analyze_recent_performance(self):
        """Analyze recent prediction accuracy to auto-adjust"""
        
        cursor = self.conn.cursor(dictionary=True)
        
        # Get last 14 days of predictions vs actuals
        cursor.execute("""
            SELECT 
                prediction_date,
                predicted_orders,
                actual_orders,
                DAYNAME(prediction_date) as day_name
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND predicted_orders IS NOT NULL
            AND prediction_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            ORDER BY prediction_date DESC
        """)
        
        recent = cursor.fetchall()
        
        adjustments = {}
        
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            day_data = [r for r in recent if r['day_name'] == day]
            if day_data:
                # Calculate average over/under prediction
                errors = [(float(d['actual_orders']) / d['predicted_orders']) 
                         for d in day_data if d['predicted_orders'] > 0]
                if errors:
                    avg_error = np.mean(errors)
                    if avg_error > 1.1:  # Consistently under-predicting
                        adjustments[day] = 1.05  # Boost by 5%
                        print(f"  📈 Auto-adjusting {day}: +5% (was under-predicting)")
                    elif avg_error < 0.9:  # Consistently over-predicting
                        adjustments[day] = 0.95  # Reduce by 5%
                        print(f"  📉 Auto-adjusting {day}: -5% (was over-predicting)")
        
        cursor.close()
        return adjustments
    
    def train_enhanced(self):
        """Train the enhanced model with all improvements"""
        
        # First, run the basic training from advanced_predictor
        cursor = self.conn.cursor(dictionary=True)
        
        # Get baseline
        cursor.execute("""
            SELECT 
                AVG(actual_orders) as avg,
                STD(actual_orders) as std_dev,
                MIN(actual_orders) as min_orders,
                MAX(actual_orders) as max_orders
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
        """)
        
        baseline = cursor.fetchone()
        self.base_average = float(baseline['avg'])
        self.std_deviation = float(baseline['std_dev'])
        
        print(f"📊 Enhanced Model Training")
        print(f"  Base Average: {self.base_average:.0f} items")
        print(f"  QC Capacity: {self.qc_capacity:.0f} items")
        
        # Get day patterns (simplified for brevity)
        cursor.execute("""
            SELECT 
                DAYNAME(prediction_date) as day,
                AVG(actual_orders) as avg_orders,
                STD(actual_orders) as std_dev
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY DAYNAME(prediction_date)
        """)
        
        for row in cursor.fetchall():
            self.patterns['day_of_week'][row['day']] = {
                'multiplier': float(row['avg_orders']) / self.base_average,
                'average': float(row['avg_orders']),
                'std_dev': float(row['std_dev'])
            }
        
        # Analyze recent performance for auto-adjustment
        print("\n🔧 Auto-adjustments based on recent performance:")
        self.recent_adjustments = self.analyze_recent_performance()
        
        cursor.close()
        return True
    
    def predict_enhanced(self, target_date, verbose=False):
        """Make enhanced prediction with all factors"""
        
        # Start with base
        prediction = self.base_average
        factors = []
        confidence = 75
        
        # 1. Day of week (with auto-adjustment)
        day_name = target_date.strftime('%A')
        if day_name in self.patterns['day_of_week']:
            day_mult = self.patterns['day_of_week'][day_name]['multiplier']
            
            # Apply auto-adjustment if available
            if hasattr(self, 'recent_adjustments') and day_name in self.recent_adjustments:
                day_mult *= self.recent_adjustments[day_name]
                factors.append(f"{day_name}(adjusted): ×{day_mult:.2f}")
            else:
                factors.append(f"{day_name}: ×{day_mult:.2f}")
            
            prediction *= day_mult
        
        # 2. Holiday detection
        holiday_info = self.detect_holidays(target_date)
        if holiday_info['multiplier'] != 1.0:
            prediction *= holiday_info['multiplier']
            factors.append(f"{holiday_info['name']}: ×{holiday_info['multiplier']:.2f}")
            
            # Adjust confidence for holidays
            if holiday_info['is_holiday']:
                confidence -= 10  # Less confident on holidays
        
        # 3. Customer patterns
        customer_pattern = self.detect_customer_patterns(target_date)
        if customer_pattern['multiplier'] != 1.0:
            prediction *= customer_pattern['multiplier']
            factors.append(f"{customer_pattern['pattern']}: ×{customer_pattern['multiplier']:.2f}")
        
        # 4. QC Capacity constraint
        qc_result = self.apply_qc_constraint(prediction, target_date)
        
        final_prediction = {
            'date': target_date,
            'day_name': day_name,
            'predicted_orders': int(qc_result['constrained_prediction']),
            'unconstrained_prediction': int(qc_result['original_prediction']),
            'confidence': confidence,
            'factors': factors,
            'qc_constraint': qc_result['constraint_applied'],
            'overflow': qc_result['overflow']
        }
        
        if qc_result['constraint_applied']:
            final_prediction['warning'] = qc_result['reason']
            final_prediction['suggestion'] = qc_result['suggestion']
        
        # Add bounds
        if day_name in self.patterns['day_of_week']:
            std_dev = self.patterns['day_of_week'][day_name]['std_dev']
        else:
            std_dev = self.std_deviation
        
        final_prediction['lower_bound'] = max(0, int(final_prediction['predicted_orders'] - (2 * std_dev)))
        final_prediction['upper_bound'] = int(final_prediction['predicted_orders'] + (2 * std_dev))
        
        if verbose:
            print(f"\n📅 {target_date} ({day_name})")
            print(f"  Prediction: {final_prediction['predicted_orders']} items")
            if qc_result['constraint_applied']:
                print(f"  ⚠️ QC Constrained from {qc_result['original_prediction']}")
                print(f"  💡 {qc_result['suggestion']}")
            print(f"  Factors: {', '.join(factors)}")
            print(f"  Range: {final_prediction['lower_bound']}-{final_prediction['upper_bound']}")
            print(f"  Confidence: {confidence}%")
        
        return final_prediction
    
    def simulate_week_with_constraints(self, start_date=None):
        """Simulate a week showing QC constraints and overflow"""
        
        if not start_date:
            start_date = datetime.now().date()
        
        print("\n" + "=" * 70)
        print("📊 WEEKLY PREDICTION WITH OPERATIONAL CONSTRAINTS")
        print("=" * 70)
        
        weekly_total = 0
        weekly_overflow = 0
        
        for i in range(7):
            date = start_date + timedelta(days=i)
            pred = self.predict_enhanced(date, verbose=True)
            
            weekly_total += pred['predicted_orders']
            weekly_overflow += pred['overflow']
        
        print("\n" + "-" * 70)
        print(f"📈 WEEKLY SUMMARY:")
        print(f"  Total Predicted: {weekly_total:,} items")
        print(f"  Daily Average: {weekly_total/7:.0f} items")
        
        if weekly_overflow > 0:
            print(f"  ⚠️ QC Overflow: {weekly_overflow:,} items")
            print(f"  💡 Recommendation: Schedule {weekly_overflow/150:.0f} overtime hours")
        
        return {
            'weekly_total': weekly_total,
            'weekly_overflow': weekly_overflow,
            'daily_average': weekly_total/7
        }
    
    def close(self):
        if self.conn:
            self.conn.close()
