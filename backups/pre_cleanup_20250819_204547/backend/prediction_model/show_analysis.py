#!/usr/bin/env python3
"""
Show real demand vs capacity
"""

from enhanced_predictor import EnhancedWarehousePredictor
from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor(dictionary=True)

print(f"\n{'='*70}")
print("📊 DEMAND vs CAPACITY - NEXT 7 DAYS")
print(f"{'='*70}\n")

# Get predictions
cursor.execute("""
    SELECT 
        prediction_date,
        DAYNAME(prediction_date) as day,
        predicted_orders
    FROM order_predictions
    WHERE prediction_date >= CURDATE()
    ORDER BY prediction_date
    LIMIT 7
""")

predictor = EnhancedWarehousePredictor()
predictor.train_enhanced()

for row in cursor.fetchall():
    day = row['day']
    qc_limit = row['predicted_orders']
    
    # Get real demand
    if day in predictor.patterns['day_of_week']:
        demand = int(predictor.patterns['day_of_week'][day]['average'])
    else:
        demand = 1138
    
    overflow = max(0, demand - qc_limit)
    status = "⚠️ OVERFLOW" if overflow > 0 else "✅ OK"
    
    print(f"{row['prediction_date']} ({day:9}): Demand={demand:4} → QC={qc_limit:4} [{status}]")
    if overflow > 0:
        print(f"{'':23} Need {overflow/150:.1f} overtime hours")

cursor.close()
conn.close()
predictor.close()
