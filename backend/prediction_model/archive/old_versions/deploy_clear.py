#!/usr/bin/env python3
"""
Deploy predictions showing BOTH real demand and constrained capacity
"""

from enhanced_predictor import EnhancedWarehousePredictor
from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta
import json

def deploy_with_clarity():
    print("\n🚀 Generating Predictions with CLEAR demand visibility")
    print("=" * 80)
    
    predictor = EnhancedWarehousePredictor()
    predictor.train_enhanced()
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Add columns to store both values if not exists
    cursor.execute("""
        ALTER TABLE order_predictions 
        ADD COLUMN IF NOT EXISTS unconstrained_demand INT,
        ADD COLUMN IF NOT EXISTS qc_overflow INT,
        ADD COLUMN IF NOT EXISTS needs_overtime BOOLEAN DEFAULT FALSE
    """)
    
    print("\n📊 NEXT 7 DAYS - SHOWING REAL DEMAND:\n")
    print(f"{'Date':<12} {'Day':<10} {'REAL DEMAND':<12} {'→':<3} {'QC LIMITED':<12} {'OVERFLOW':<10}")
    print("-" * 70)
    
    for i in range(7):
        date = datetime.now().date() + timedelta(days=i)
        day_name = date.strftime('%A')
        
        # Get UNCONSTRAINED demand
        if day_name in predictor.patterns['day_of_week']:
            unconstrained = int(predictor.patterns['day_of_week'][day_name]['average'])
        else:
            unconstrained = int(predictor.base_average)
        
        # Get CONSTRAINED prediction
        result = predictor.predict_enhanced(date, verbose=False)
        constrained = result['predicted_orders']
        overflow = result.get('overflow', 0)
        
        # Store BOTH in database
        cursor.execute("""
            INSERT INTO order_predictions 
            (prediction_date, predicted_orders, unconstrained_demand, 
             qc_overflow, needs_overtime, confidence_score)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            predicted_orders = VALUES(predicted_orders),
            unconstrained_demand = VALUES(unconstrained_demand),
            qc_overflow = VALUES(qc_overflow),
            needs_overtime = VALUES(needs_overtime),
            confidence_score = VALUES(confidence_score)
        """, (
            date,
            constrained,  # What we can handle
            unconstrained,  # What's actually coming
            overflow,
            overflow > 0,
            result['confidence']
        ))
        
        # Print clear output
        overflow_str = f"{overflow} items" if overflow > 0 else "—"
        print(f"{str(date):<12} {day_name:<10} {unconstrained:>10} → {constrained:>10}   {overflow_str:<10}")
    
    conn.commit()
    print("-" * 70)
    print("\n✅ Stored BOTH numbers in database:")
    print("   • unconstrained_demand = What's actually coming")
    print("   • predicted_orders = What we can QC")
    print("   • qc_overflow = What will be delayed")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    deploy_with_clarity()
