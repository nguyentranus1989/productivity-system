#!/usr/bin/env python3
"""
Production deployment of enhanced predictor
Generates predictions and stores them with all metadata
"""

from enhanced_predictor import EnhancedWarehousePredictor
from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta
import json
import logging

logging.basicConfig(
    filename='enhanced_predictions.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def deploy_enhanced_predictions():
    """Generate and store enhanced predictions"""
    
    try:
        print(f"\n🚀 Generating Enhanced Predictions - {datetime.now()}")
        print("=" * 60)
        
        # Initialize
        predictor = EnhancedWarehousePredictor()
        predictor.train_enhanced()
        
        # Database connection
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # First, create extended predictions table if needed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions_enhanced (
                prediction_date DATE PRIMARY KEY,
                predicted_orders INT,
                lower_bound INT,
                upper_bound INT,
                confidence_score INT,
                factors JSON,
                qc_constrained BOOLEAN DEFAULT FALSE,
                overflow_items INT DEFAULT 0,
                holiday_name VARCHAR(100),
                warnings TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Generate predictions for next 30 days
        for i in range(30):
            date = datetime.now().date() + timedelta(days=i)
            result = predictor.predict_enhanced(date, verbose=False)
            
            # Prepare data for storage
            factors_json = json.dumps(result['factors'])
            holiday_info = predictor.detect_holidays(date)
            
            # Store in both tables
            # 1. Original predictions table (for compatibility)
            cursor.execute("""
                INSERT INTO order_predictions 
                (prediction_date, predicted_orders, confidence_score)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                predicted_orders = VALUES(predicted_orders),
                confidence_score = VALUES(confidence_score)
            """, (date, result['predicted_orders'], result['confidence']))
            
            # 2. Enhanced predictions table (with all metadata)
            cursor.execute("""
                INSERT INTO predictions_enhanced
                (prediction_date, predicted_orders, lower_bound, upper_bound,
                 confidence_score, factors, qc_constrained, overflow_items,
                 holiday_name, warnings)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                predicted_orders = VALUES(predicted_orders),
                lower_bound = VALUES(lower_bound),
                upper_bound = VALUES(upper_bound),
                confidence_score = VALUES(confidence_score),
                factors = VALUES(factors),
                qc_constrained = VALUES(qc_constrained),
                overflow_items = VALUES(overflow_items),
                holiday_name = VALUES(holiday_name),
                warnings = VALUES(warnings)
            """, (
                date,
                result['predicted_orders'],
                result['lower_bound'],
                result['upper_bound'],
                result['confidence'],
                factors_json,
                result['qc_constraint'],
                result['overflow'],
                holiday_info['name'],
                result.get('warning', None)
            ))
            
            # Print summary
            if i < 7:  # Detail for next week
                print(f"✓ {date} ({result['day_name']}): {result['predicted_orders']} items", end="")
                if result['qc_constraint']:
                    print(f" [QC Limited]", end="")
                if holiday_info['name']:
                    print(f" [{holiday_info['name']}]", end="")
                print()
        
        conn.commit()
        
        # Log summary
        logging.info(f"Generated 30 predictions successfully")
        print(f"\n✅ Enhanced predictions saved for next 30 days!")
        
        # Generate alerts if needed
        cursor.execute("""
            SELECT prediction_date, overflow_items, warnings
            FROM predictions_enhanced
            WHERE prediction_date >= CURDATE()
            AND (overflow_items > 0 OR warnings IS NOT NULL)
            ORDER BY prediction_date
            LIMIT 7
        """)
        
        alerts = cursor.fetchall()
        if alerts:
            print("\n⚠️ OPERATIONAL ALERTS:")
            for alert in alerts:
                print(f"  {alert[0]}: Overflow {alert[1]} items - {alert[2]}")
        
        cursor.close()
        conn.close()
        predictor.close()
        
    except Exception as e:
        logging.error(f"Prediction generation failed: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    deploy_enhanced_predictions()
