#!/usr/bin/env python3
"""
Advanced Warehouse Prediction Model v2
Multi-factor analysis with machine learning components
"""

from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
import logging
import json

class AdvancedWarehousePredictor:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        self.base_average = 0
        self.patterns = {
            'day_of_week': {},
            'week_of_month': {},
            'month': {},
            'trends': {},
            'special_events': {},
            'customer_patterns': {}
        }
        self.accuracy_history = []
        
    def train_comprehensive(self):
        """Train on multiple factors for better accuracy"""
        cursor = self.conn.cursor(dictionary=True)
        
        print("🧠 Training Advanced Prediction Model...")
        print("=" * 60)
        
        # 1. BASELINE CALCULATION
        cursor.execute("""
            SELECT 
                AVG(actual_orders) as avg,
                STD(actual_orders) as std_dev,
                MIN(actual_orders) as min_orders,
                MAX(actual_orders) as max_orders,
                COUNT(*) as total_days
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
        """)
        
        baseline = cursor.fetchone()
        self.base_average = float(baseline['avg'])
        self.std_deviation = float(baseline['std_dev'])
        
        print(f"\n📊 BASELINE METRICS:")
        print(f"  Average: {self.base_average:.0f} items/day")
        print(f"  Std Dev: {self.std_deviation:.0f}")
        print(f"  Range: {baseline['min_orders']}-{baseline['max_orders']}")
        print(f"  Dataset: {baseline['total_days']} days")
        
        # 2. DAY OF WEEK PATTERNS (with variance)
        cursor.execute("""
            SELECT 
                DAYNAME(prediction_date) as day,
                AVG(actual_orders) as avg_orders,
                STD(actual_orders) as std_dev,
                MIN(actual_orders) as min_orders,
                MAX(actual_orders) as max_orders,
                COUNT(*) as count
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY DAYNAME(prediction_date)
        """)
        
        print(f"\n📅 DAY-OF-WEEK PATTERNS:")
        print("-" * 60)
        print(f"{'Day':<12} {'Avg':>8} {'StdDev':>8} {'Min':>8} {'Max':>8} {'Mult':>8}")
        print("-" * 60)
        
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        results = cursor.fetchall()
        sorted_results = sorted(results, key=lambda x: day_order.index(x['day']) if x['day'] in day_order else 999)
        
        for row in sorted_results:
            multiplier = float(row['avg_orders']) / self.base_average
            self.patterns['day_of_week'][row['day']] = {
                'multiplier': multiplier,
                'average': float(row['avg_orders']),
                'std_dev': float(row['std_dev']),
                'min': row['min_orders'],
                'max': row['max_orders'],
                'confidence': 100 - (float(row['std_dev']) / float(row['avg_orders']) * 100)
            }
            print(f"{row['day']:<12} {row['avg_orders']:>8.0f} {row['std_dev']:>8.0f} "
                  f"{row['min_orders']:>8} {row['max_orders']:>8} {multiplier:>8.2f}x")
        
        # 3. WEEK OF MONTH PATTERNS
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN DAY(prediction_date) <= 7 THEN 'Week 1'
                    WHEN DAY(prediction_date) <= 14 THEN 'Week 2'
                    WHEN DAY(prediction_date) <= 21 THEN 'Week 3'
                    WHEN DAY(prediction_date) <= 28 THEN 'Week 4'
                    ELSE 'Week 5'
                END as week_of_month,
                AVG(actual_orders) as avg_orders,
                COUNT(*) as count
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY week_of_month
            ORDER BY week_of_month
        """)
        
        print(f"\n📆 WEEK-OF-MONTH PATTERNS:")
        print("-" * 40)
        
        for row in cursor.fetchall():
            multiplier = float(row['avg_orders']) / self.base_average
            self.patterns['week_of_month'][row['week_of_month']] = multiplier
            print(f"  {row['week_of_month']}: {row['avg_orders']:.0f} items (×{multiplier:.2f})")
        
        # 4. MONTHLY SEASONALITY
        cursor.execute("""
            SELECT 
                MONTH(prediction_date) as month_num,
                MONTHNAME(prediction_date) as month,
                AVG(actual_orders) as avg_orders,
                COUNT(*) as count
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY MONTH(prediction_date), MONTHNAME(prediction_date)
            ORDER BY month_num
        """)
        
        print(f"\n📈 MONTHLY TRENDS:")
        print("-" * 40)
        
        for row in cursor.fetchall():
            multiplier = float(row['avg_orders']) / self.base_average
            self.patterns['month'][row['month_num']] = {
                'name': row['month'],
                'multiplier': multiplier,
                'average': float(row['avg_orders'])
            }
            print(f"  {row['month']:<12}: {row['avg_orders']:.0f} items (×{multiplier:.2f})")
        
        # 5. TREND ANALYSIS (Growth/Decline)
        cursor.execute("""
            SELECT 
                prediction_date,
                actual_orders
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            ORDER BY prediction_date
        """)
        
        orders_timeline = cursor.fetchall()
        if len(orders_timeline) > 30:
            # Calculate trend using linear regression
            days = np.arange(len(orders_timeline))
            values = np.array([float(x['actual_orders']) for x in orders_timeline])
            
            # Simple linear regression
            slope, intercept = np.polyfit(days, values, 1)
            daily_growth = slope
            monthly_growth = slope * 30
            
            self.patterns['trends']['daily_growth'] = daily_growth
            self.patterns['trends']['monthly_growth'] = monthly_growth
            
            print(f"\n📊 TREND ANALYSIS:")
            print(f"  Daily growth: {daily_growth:+.1f} items/day")
            print(f"  Monthly growth: {monthly_growth:+.1f} items/month")
            print(f"  Growth rate: {(monthly_growth/self.base_average*100):+.1f}%/month")
        
        # 6. SPECIAL PATTERNS (After holidays, First Monday, etc.)
        cursor.execute("""
            SELECT 
                CASE
                    WHEN DAY(prediction_date) <= 7 AND DAYNAME(prediction_date) = 'Monday' 
                        THEN 'First Monday'
                    WHEN DAY(prediction_date) >= 25 
                        THEN 'Month End'
                    ELSE 'Regular'
                END as pattern_type,
                AVG(actual_orders) as avg_orders,
                COUNT(*) as count
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY pattern_type
        """)
        
        print(f"\n✨ SPECIAL PATTERNS:")
        print("-" * 40)
        
        regular_avg = self.base_average
        for row in cursor.fetchall():
            if row['pattern_type'] == 'Regular':
                regular_avg = float(row['avg_orders'])
                
        cursor.execute("""
            SELECT 
                CASE
                    WHEN DAY(prediction_date) <= 7 AND DAYNAME(prediction_date) = 'Monday' 
                        THEN 'First Monday'
                    WHEN DAY(prediction_date) >= 25 
                        THEN 'Month End'
                    ELSE 'Regular'
                END as pattern_type,
                AVG(actual_orders) as avg_orders,
                COUNT(*) as count
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY pattern_type
        """)
        
        for row in cursor.fetchall():
            if row['pattern_type'] != 'Regular':
                boost = float(row['avg_orders']) / regular_avg
                self.patterns['special_events'][row['pattern_type']] = boost
                print(f"  {row['pattern_type']}: {row['avg_orders']:.0f} items (×{boost:.2f} boost)")
        
        cursor.close()
        print("\n✅ Model training complete!")
        return True
    
    def predict_advanced(self, target_date, use_all_factors=True):
        """Generate prediction using all factors"""
        
        # Start with base
        prediction = self.base_average
        confidence_factors = []
        adjustments = []
        
        # 1. Day of week factor (strongest signal)
        day_name = target_date.strftime('%A')
        if day_name in self.patterns['day_of_week']:
            day_data = self.patterns['day_of_week'][day_name]
            day_mult = day_data['multiplier']
            prediction *= day_mult
            confidence_factors.append(day_data['confidence'])
            adjustments.append(f"Day({day_name}): ×{day_mult:.2f}")
        
        if use_all_factors:
            # 2. Week of month factor
            day_of_month = target_date.day
            if day_of_month <= 7:
                week = 'Week 1'
            elif day_of_month <= 14:
                week = 'Week 2'
            elif day_of_month <= 21:
                week = 'Week 3'
            elif day_of_month <= 28:
                week = 'Week 4'
            else:
                week = 'Week 5'
                
            if week in self.patterns['week_of_month']:
                week_mult = self.patterns['week_of_month'][week]
                prediction *= week_mult
                adjustments.append(f"{week}: ×{week_mult:.2f}")
            
            # 3. Monthly seasonality
            month_num = target_date.month
            if month_num in self.patterns['month']:
                # Only apply if we have data for this month
                month_mult = self.patterns['month'][month_num]['multiplier']
                # Dampen the effect (use sqrt to reduce impact)
                month_effect = 1 + (month_mult - 1) * 0.3
                prediction *= month_effect
                adjustments.append(f"Month: ×{month_effect:.2f}")
            
            # 4. Trend adjustment
            if 'daily_growth' in self.patterns['trends']:
                # Days since training data
                days_since = (target_date - datetime(2025, 7, 31).date()).days
                if days_since > 0:
                    trend_adjustment = 1 + (self.patterns['trends']['daily_growth'] * days_since / self.base_average)
                    prediction *= trend_adjustment
                    adjustments.append(f"Trend: ×{trend_adjustment:.2f}")
            
            # 5. Special events
            if day_of_month <= 7 and day_name == 'Monday':
                if 'First Monday' in self.patterns['special_events']:
                    special_mult = self.patterns['special_events']['First Monday']
                    prediction *= special_mult
                    adjustments.append(f"First Monday: ×{special_mult:.2f}")
        
        # Calculate confidence
        if confidence_factors:
            base_confidence = np.mean(confidence_factors)
        else:
            base_confidence = 75
            
        # Adjust confidence based on how far out we're predicting
        days_out = (target_date - datetime.now().date()).days
        confidence = max(50, base_confidence - (days_out * 2))
        
        # Apply bounds (don't predict outside historical range)
        min_historical = 200  # You can get this from data
        max_historical = 3000  # You can get this from data
        prediction = max(min_historical, min(max_historical, prediction))
        
        return {
            'date': target_date,
            'day_name': day_name,
            'predicted_orders': int(prediction),
            'confidence': int(confidence),
            'adjustments': adjustments,
            'method': 'advanced_multi_factor'
        }
    
    def predict_with_bounds(self, target_date):
        """Predict with confidence intervals"""
        
        base_prediction = self.predict_advanced(target_date)
        
        # Get historical variance for this day
        day_name = target_date.strftime('%A')
        if day_name in self.patterns['day_of_week']:
            std_dev = self.patterns['day_of_week'][day_name]['std_dev']
        else:
            std_dev = self.std_deviation
        
        # Calculate bounds (95% confidence interval)
        lower_bound = int(base_prediction['predicted_orders'] - (2 * std_dev))
        upper_bound = int(base_prediction['predicted_orders'] + (2 * std_dev))
        
        base_prediction['lower_bound'] = max(0, lower_bound)
        base_prediction['upper_bound'] = upper_bound
        base_prediction['likely_range'] = f"{base_prediction['lower_bound']}-{base_prediction['upper_bound']}"
        
        return base_prediction
    
    def backtest(self, test_start='2025-07-01', test_end='2025-07-31'):
        """Test model accuracy on historical data"""
        
        cursor = self.conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT prediction_date, actual_orders
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN %s AND %s
            ORDER BY prediction_date
        """, (test_start, test_end))
        
        test_data = cursor.fetchall()
        
        errors = []
        results = []
        
        print(f"\n🧪 BACKTESTING on {len(test_data)} days:")
        print("-" * 60)
        
        for row in test_data:
            pred = self.predict_advanced(row['prediction_date'], use_all_factors=True)
            actual = row['actual_orders']
            predicted = pred['predicted_orders']
            error = abs(predicted - actual)
            error_pct = (error / actual * 100) if actual > 0 else 0
            
            errors.append(error_pct)
            results.append({
                'date': row['prediction_date'],
                'actual': actual,
                'predicted': predicted,
                'error': error,
                'error_pct': error_pct
            })
        
        # Calculate metrics
        mae = np.mean([r['error'] for r in results])
        mape = np.mean(errors)
        accuracy = 100 - mape
        
        print(f"\n📊 BACKTEST RESULTS:")
        print(f"  Mean Absolute Error: {mae:.0f} items")
        print(f"  Mean Absolute % Error: {mape:.1f}%")
        print(f"  Model Accuracy: {accuracy:.1f}%")
        
        # Show worst predictions
        worst = sorted(results, key=lambda x: x['error_pct'], reverse=True)[:5]
        print(f"\n❌ Worst Predictions:")
        for r in worst:
            print(f"  {r['date']}: Predicted {r['predicted']}, Actual {r['actual']} ({r['error_pct']:.1f}% error)")
        
        # Show best predictions
        best = sorted(results, key=lambda x: x['error_pct'])[:5]
        print(f"\n✅ Best Predictions:")
        for r in best:
            print(f"  {r['date']}: Predicted {r['predicted']}, Actual {r['actual']} ({r['error_pct']:.1f}% error)")
        
        cursor.close()
        return accuracy
    
    def close(self):
        if self.conn:
            self.conn.close()
