#!/usr/bin/env python3
from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta
import logging

class WarehousePredictor:
    def __init__(self):
        self.conn = None
        self.day_multipliers = {}
        self.base_average = 0
        self.connect()
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            logging.info("Database connected")
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            raise
    
    def train(self):
        """Train model on historical data"""
        cursor = self.conn.cursor(dictionary=True)
        
        # Get overall average
        cursor.execute("""
            SELECT AVG(actual_orders) as avg
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
        """)
        
        result = cursor.fetchone()
        self.base_average = float(result['avg'])
        
        print(f"📊 Base daily average: {self.base_average:.0f} items")
        
        # Get day patterns - SIMPLIFIED WITHOUT ORDER BY
        cursor.execute("""
            SELECT 
                DAYNAME(prediction_date) as day,
                AVG(actual_orders) as avg_orders,
                COUNT(*) as count
            FROM order_predictions
            WHERE actual_orders IS NOT NULL
            AND prediction_date BETWEEN '2025-01-01' AND '2025-07-31'
            GROUP BY DAYNAME(prediction_date)
        """)
        
        print("\n📅 Day-of-week patterns discovered:")
        print("-" * 50)
        
        # Store results first
        results = cursor.fetchall()
        
        # Sort days in correct order in Python
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        sorted_results = sorted(results, key=lambda x: day_order.index(x['day']) if x['day'] in day_order else 999)
        
        for row in sorted_results:
            multiplier = float(row['avg_orders']) / self.base_average
            self.day_multipliers[row['day']] = multiplier
            print(f"  {row['day']:10} : {row['avg_orders']:6.0f} items (×{multiplier:.2f}) [{row['count']} days]")
        
        cursor.close()
        return True
    
    def predict(self, target_date):
        """Make prediction for a specific date"""
        day_name = target_date.strftime('%A')
        multiplier = self.day_multipliers.get(day_name, 1.0)
        prediction = int(self.base_average * multiplier)
        
        # Calculate confidence based on how much data we have
        confidence = 75  # Base confidence
        if len(self.day_multipliers) == 7:
            confidence = 85  # We have full week data
        
        return {
            'date': target_date,
            'day_name': day_name,
            'predicted_orders': prediction,
            'confidence': confidence,
            'multiplier': multiplier
        }
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
