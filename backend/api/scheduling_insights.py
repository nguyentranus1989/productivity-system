from flask import jsonify
from database.db_manager import DatabaseManager
from datetime import datetime, timedelta
from utils.timezone_helpers import TimezoneHelper

def get_scheduling_insights():
    db = DatabaseManager()
    tz_helper = TimezoneHelper()

    ct_date = tz_helper.get_current_ct_date()
    date_14d_ago = ct_date - timedelta(days=14)

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
        AND prediction_date >= %s
        GROUP BY DAYNAME(prediction_date)
    """, (date_14d_ago,))

    return jsonify(insights)
