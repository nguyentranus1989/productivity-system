#!/usr/bin/env python3
"""
Simple Order Prediction Engine
"""

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class OrderPredictor:
    """Predicts daily order volumes based on historical patterns"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        
        # Day-of-week multipliers based on patterns
        self.day_multipliers = {
            'Monday': 1.20,
            'Tuesday': 0.95,
            'Wednesday': 0.90,
            'Thursday': 1.10,
            'Friday': 1.30,
            'Saturday': 0.80,
            'Sunday': 0.70
        }
    
    def predict_week(self, start_date: datetime):
        """Predict orders for a week"""
        predictions = {}
        
        # Make sure we start on Monday
        while start_date.weekday() != 0:
            start_date -= timedelta(days=1)
        
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            day_name = current_date.strftime('%A')
            
            # Get average from historical data
            query = """
                SELECT AVG(actual_orders) as avg_orders
                FROM order_predictions
                WHERE actual_orders IS NOT NULL
                AND DAYNAME(prediction_date) = %s
            """
            
            result = self.db.execute_one(query, (day_name,))
            base_value = int(result['avg_orders']) if result and result['avg_orders'] else 500
            
            predictions[current_date.strftime('%Y-%m-%d')] = {
                'date': current_date.strftime('%Y-%m-%d'),
                'day_name': day_name,
                'predicted_orders': base_value,
                'confidence': 75
            }
        
        return predictions
