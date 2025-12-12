from flask import Blueprint, jsonify
from database.db_manager import DatabaseManager
from datetime import datetime

schedule_bp = Blueprint('intelligent_schedule', __name__)

# Lazy-loaded database manager
_db = None

def get_db():
    """Get database manager instance (lazy initialization)"""
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db

@schedule_bp.route('/api/schedule/weekly', methods=['GET'])
def get_weekly_schedule():
    """Get weekly schedule with predictions and assignments"""
    
    # Get predictions
    predictions_query = """
    SELECT 
        prediction_date as date,
        DAYNAME(prediction_date) as day_name,
        predicted_orders,
        confidence_score,
        qc_constrained,
        overflow_items
    FROM predictions_enhanced
    WHERE prediction_date >= CURDATE()
        AND prediction_date < DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    ORDER BY prediction_date
    """
    predictions = get_db().execute_query(predictions_query)
    
    # Get top performers by station
    performance_query = """
    SELECT 
        e.name,
        al.activity_type as station,
        SUM(al.items_count) as total_items,
        COUNT(DISTINCT DATE(al.window_start)) as days_worked,
        ROW_NUMBER() OVER (PARTITION BY al.activity_type 
                          ORDER BY SUM(al.items_count) DESC) as rank_num
    FROM employees e
    JOIN activity_logs al ON e.id = al.employee_id
    WHERE al.window_start >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
    GROUP BY e.id, e.name, al.activity_type
    HAVING days_worked >= 3
    """
    performance = get_db().execute_query(performance_query)
    
    return jsonify({
        'predictions': predictions,
        'performance': performance,
        'generated_at': datetime.now().isoformat()
    })

@schedule_bp.route('/api/schedule/staffing-needs', methods=['GET'])
def get_staffing_needs():
    """Calculate staffing needs based on predictions"""
    
    query = """
    SELECT 
        prediction_date,
        DAYNAME(prediction_date) as day_name,
        predicted_orders,
        -- Calculate hours needed per station
        ROUND(predicted_orders / 40, 1) as heat_press_hours,
        ROUND(predicted_orders / 45, 1) as qc_hours,
        ROUND(predicted_orders / 133, 1) as film_hours,
        ROUND(predicted_orders / 200, 1) as picking_hours,
        ROUND(predicted_orders / 200, 1) as labeling_hours,
        -- Calculate people needed (8-hour shifts)
        CEILING(predicted_orders / 40 / 8) as heat_press_people,
        CEILING(predicted_orders / 45 / 8) as qc_people,
        CEILING(predicted_orders / 133 / 8) as film_people,
        CEILING(predicted_orders / 200 / 8) as picking_people
    FROM predictions_enhanced
    WHERE prediction_date >= CURDATE()
        AND prediction_date < DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    ORDER BY prediction_date
    """
    
    needs = get_db().execute_query(query)
    return jsonify(needs)
