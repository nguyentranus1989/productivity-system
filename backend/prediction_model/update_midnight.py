#!/usr/bin/env python3
"""
Midnight Learning Script - Updates predictions with actual QC data
Runs at 11:59 PM to capture full day's data
"""

from db_config import DB_CONFIG
import mysql.connector
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(
    filename='midnight_learning.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def midnight_learning():
    """Update predictions with actual QC data from today"""
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Today's date (since we're running at 11:59 PM)
    today = datetime.now().date()
    
    print(f"\n{'='*60}")
    print(f"🌙 MIDNIGHT LEARNING - {today}")
    print(f"{'='*60}")
    
    # Get actual QC passed for TODAY
    cursor.execute("""
        SELECT 
            SUM(items_count) as actual_qc,
            COUNT(DISTINCT employee_id) as qc_staff_count,
            MIN(window_start) as first_scan,
            MAX(window_end) as last_scan
        FROM activity_logs
        WHERE activity_type IN ('QC Passed', 'QC/Outbound')
        AND DATE(window_start) = %s
    """, (today,))
    
    result = cursor.fetchone()
    actual_qc = result[0] if result[0] else 0
    staff_count = result[1] if result[1] else 0
    
    # Get what we predicted
    cursor.execute("""
        SELECT predicted_orders, confidence_score
        FROM order_predictions
        WHERE prediction_date = %s
    """, (today,))
    
    pred_result = cursor.fetchone()
    
    if pred_result and actual_qc > 0:
        predicted = pred_result[0]
        error = abs(predicted - actual_qc)
        error_pct = (error / actual_qc * 100) if actual_qc > 0 else 0
        
        # Update with actual
        cursor.execute("""
            UPDATE order_predictions
            SET actual_orders = %s
            WHERE prediction_date = %s
        """, (actual_qc, today))
        
        conn.commit()
        
        # Display results
        print(f"\n📊 TODAY'S RESULTS:")
        print(f"  Predicted: {predicted} items")
        print(f"  Actual QC: {actual_qc} items")
        print(f"  Error: {error} items ({error_pct:.1f}%)")
        print(f"  QC Staff: {staff_count} people")
        
        # Determine accuracy level
        if error_pct < 5:
            status = "🎯 EXCELLENT - Near perfect prediction!"
        elif error_pct < 10:
            status = "✅ GREAT - Very accurate"
        elif error_pct < 20:
            status = "👍 GOOD - Acceptable accuracy"
        else:
            status = "⚠️ NEEDS IMPROVEMENT - Check for special events"
        
        print(f"  Status: {status}")
        
        # Log for pattern analysis
        logging.info(f"Date: {today}, Predicted: {predicted}, Actual: {actual_qc}, Error: {error_pct:.1f}%")
        
        # Check if we need to adjust patterns
        if error_pct > 20:
            print(f"\n⚠️ HIGH ERROR DETECTED - Analyzing why...")
            
            # Check if this was a special event
            day_name = today.strftime('%A')
            
            cursor.execute("""
                SELECT AVG(actual_orders) as typical
                FROM order_predictions
                WHERE DAYNAME(prediction_date) = %s
                AND actual_orders IS NOT NULL
                AND prediction_date < %s
                AND prediction_date >= DATE_SUB(%s, INTERVAL 30 DAY)
            """, (day_name, today, today))
            
            typical_result = cursor.fetchone()
            if typical_result and typical_result[0]:
                typical = typical_result[0]
                if abs(actual_qc - typical) / typical > 0.3:
                    print(f"  📌 Today was unusual for a {day_name}")
                    print(f"  📌 Typical {day_name}: {typical:.0f} items")
                    print(f"  📌 Today: {actual_qc} items")
                    print(f"  📌 Possible special event or anomaly")
        
        # Weekly summary every Sunday
        if today.weekday() == 6:  # Sunday
            print(f"\n📈 WEEKLY ACCURACY SUMMARY:")
            
            cursor.execute("""
                SELECT 
                    AVG(ABS(predicted_orders - actual_orders) / actual_orders * 100) as avg_error,
                    COUNT(*) as days_tracked
                FROM order_predictions
                WHERE actual_orders IS NOT NULL
                AND predicted_orders IS NOT NULL
                AND prediction_date >= DATE_SUB(%s, INTERVAL 7 DAY)
                AND prediction_date <= %s
            """, (today, today))
            
            week_result = cursor.fetchone()
            if week_result:
                weekly_accuracy = 100 - (week_result[0] if week_result[0] else 0)
                print(f"  Week Accuracy: {weekly_accuracy:.1f}%")
                print(f"  Days Tracked: {week_result[1]}")
                
                if weekly_accuracy < 75:
                    print(f"  💡 Recommendation: Review and retrain model")
    else:
        print(f"\n❌ No QC data found for {today}")
        print(f"   Possible reasons:")
        print(f"   - No QC activity today (holiday/weekend?)")
        print(f"   - Data sync issue")
        print(f"   - Different activity type used")
    
    cursor.close()
    conn.close()
    
    print(f"\n✅ Midnight learning complete!")
    print(f"Next prediction run: Tomorrow 6:00 AM")

if __name__ == "__main__":
    midnight_learning()
