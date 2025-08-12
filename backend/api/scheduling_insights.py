from flask import jsonify
from database.db_manager import DatabaseManager
from datetime import datetime, timedelta

def get_scheduling_insights():
    db = DatabaseManager()
    
    # Get prediction accuracy by day
    insights = db.execute_all("""
        SELECT 
            DAYNAME(prediction_date) as day,
            AVG(actual_orders) as avg_actual,
            AVG(predicted_orders) as avg_predicted,
            ROUND((AVG(actual_orders)/AVG(predicted_orders)-1)*100,1) as variance_pct,
            CASE 
                WHEN AVG(actual_orders)/AVG(predicted_orders) > 1.2 THEN 'Add staff'
                WHEN AVG(actual_orders)/AVG(predicted_orders) < 0.8 THEN 'Reduce staff'
                ELSE 'Optimal'
            END as recommendation
        FROM order_predictions
        WHERE actual_orders IS NOT NULL
        AND prediction_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
        GROUP BY DAYNAME(prediction_date)
    """)
    
    return jsonify(insights)
