#!/usr/bin/env python3
"""
Enhanced deployment that CLEARLY shows real demand vs QC capacity
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
    """Generate and store enhanced predictions with CLEAR visibility"""
    
    try:
        print(f"\n🚀 Generating Enhanced Predictions - {datetime.now()}")
        print("=" * 90)
        
        # Initialize
        predictor = EnhancedWarehousePredictor()
        predictor.train_enhanced()
        
        # Database connection
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Create extended predictions table if needed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions_enhanced (
                prediction_date DATE PRIMARY KEY,
                predicted_orders INT,
                real_demand INT,
                lower_bound INT,
                upper_bound INT,
                confidence_score INT,
                factors JSON,
                qc_constrained BOOLEAN DEFAULT FALSE,
                overflow_items INT DEFAULT 0,
                holiday_name VARCHAR(100),
                warnings TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        saved_count = 0
        overflow_total = 0
        alerts = []
        
        print("\n📅 NEXT 7 DAYS FORECAST - SHOWING REAL DEMAND vs QC CAPACITY:")
        print("-" * 90)
        print(f"{'Date':<12} {'Day':<10} {'REAL DEMAND':<15} {'QC CAPACITY':<15} {'OVERFLOW':<12} {'STATUS':<20}")
        print("-" * 90)
        
        # Generate predictions for next 30 days
        for i in range(30):
            date = datetime.now().date() + timedelta(days=i)
            result = predictor.predict_enhanced(date, verbose=False)
            
            # Get the REAL DEMAND (unconstrained)
            day_name = result['day_name']
            if day_name in predictor.patterns['day_of_week']:
                real_demand = int(predictor.patterns['day_of_week'][day_name]['average'])
            else:
                real_demand = int(predictor.base_average)
            
            # What QC can actually handle
            qc_capacity = result['predicted_orders']
            overflow = result.get('overflow', 0)
            
            # Prepare data for storage
            factors_json = json.dumps(result.get('factors', []))
            holiday_info = predictor.detect_holidays(date)
            
            # Store in original predictions table
            cursor.execute("""
                INSERT INTO order_predictions 
                (prediction_date, predicted_orders, confidence_score)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                predicted_orders = VALUES(predicted_orders),
                confidence_score = VALUES(confidence_score)
            """, (
                date, 
                qc_capacity,  # Store QC-limited number
                result['confidence']
            ))
            
            # Store in enhanced table with BOTH numbers
            cursor.execute("""
                INSERT INTO predictions_enhanced
                (prediction_date, predicted_orders, real_demand, lower_bound, upper_bound,
                 confidence_score, factors, qc_constrained, overflow_items,
                 holiday_name, warnings)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                predicted_orders = VALUES(predicted_orders),
                real_demand = VALUES(real_demand),
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
                qc_capacity,  # What we can handle
                real_demand,  # What's actually coming
                result.get('lower_bound', 0),
                result.get('upper_bound', 0),
                result['confidence'],
                factors_json,
                result.get('qc_constraint', False),
                overflow,
                holiday_info.get('name'),
                result.get('warning')
            ))
            
            saved_count += 1
            overflow_total += overflow
            
            # Track alerts
            if overflow > 0:
                alerts.append({
                    'date': date,
                    'real_demand': real_demand,
                    'qc_capacity': qc_capacity,
                    'overflow': overflow
                })
            
            # Print detailed info for first week
            if i < 7:
                status = "✅ OK" if overflow == 0 else "⚠️ OVERFLOW"
                overflow_str = f"{overflow} items" if overflow > 0 else "—"
                
                print(f"{str(date):<12} {day_name:<10} {real_demand:>10} items → {qc_capacity:>10} items   {overflow_str:<12} {status:<20}")
        
        print("-" * 90)
        
        conn.commit()
        
        print(f"\n✅ {saved_count} predictions saved successfully!")
        
        # Show clear summary
        if alerts:
            print("\n⚠️ CAPACITY WARNINGS - THESE DAYS NEED ATTENTION:")
            print("-" * 90)
            for alert in alerts[:7]:  # Show first week
                overtime_hours = alert['overflow'] / 150
                print(f"  {alert['date']}: DEMAND={alert['real_demand']} but CAPACITY={alert['qc_capacity']} → Need {overtime_hours:.1f} overtime hours")
            
            print(f"\n💡 TOTAL IMPACT:")
            print(f"  • Total overflow next 30 days: {overflow_total:,} items")
            print(f"  • Days with constraints: {len(alerts)}")
            print(f"  • Overtime hours needed: {overflow_total/150:.0f} hours total")
            print(f"  • Cost of overtime: ${overflow_total/150*25:.2f}")
        else:
            print("\n✅ No capacity issues detected - current staffing is sufficient!")
        
        # Log summary
        logging.info(f"Generated {saved_count} predictions. Real demand clearly shown vs QC capacity.")
        
        cursor.close()
        conn.close()
        predictor.close()
        
        # Show the key insight
        print("\n" + "=" * 90)
        print("📊 KEY INSIGHT:")
        print("  • REAL DEMAND = What's actually coming (based on historical patterns)")
        print("  • QC CAPACITY = What we can process with current staffing")
        print("  • OVERFLOW = Items that will be delayed to next day")
        print("=" * 90)
        
        return True
        
    except Exception as e:
        logging.error(f"Prediction generation failed: {e}")
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = deploy_enhanced_predictions()
    if success:
        print("\n🎯 Use 'python3 show_real_numbers.py' to see detailed analysis")
