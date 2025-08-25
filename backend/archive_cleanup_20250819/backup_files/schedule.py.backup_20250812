from flask import Blueprint, request, jsonify
from datetime import datetime
from database.db_manager import DatabaseManager

schedule_bp = Blueprint('schedule', __name__)
db = DatabaseManager()

@schedule_bp.route('/api/schedule/save', methods=['POST'])
def save_schedule():
    try:
        data = request.json
        week_start = data.get('week_start', datetime.now().strftime('%Y-%m-%d'))
        schedule_data = data.get('schedule', [])
        print(f'Received data keys: {data.keys()}')
        print(f'Schedule data: {len(schedule_data)} employees')
        
        #         # First check if tables exist, if not create them
        #         create_tables_query = """
        #         CREATE TABLE IF NOT EXISTS schedule_master (
        #             id INT AUTO_INCREMENT PRIMARY KEY,
        #             week_start_date DATE,
        #             status ENUM('draft', 'published', 'sent') DEFAULT 'draft',
        #             created_by VARCHAR(100) DEFAULT 'Lieu',
        #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        #         );
        #         
        #         CREATE TABLE IF NOT EXISTS schedule_details (
        #             id INT AUTO_INCREMENT PRIMARY KEY,
        #             schedule_id INT,
        #             employee_name VARCHAR(100),
        #             monday_time VARCHAR(20),
        #             tuesday_time VARCHAR(20),
        #             wednesday_time VARCHAR(20),
        #             thursday_time VARCHAR(20),
        #             friday_time VARCHAR(20),
        #             saturday_time VARCHAR(20),
        #             sunday_time VARCHAR(20),
        #             FOREIGN KEY (schedule_id) REFERENCES schedule_master(id)
        #         );
        #         """
        #         
        #         # Execute table creation - handle if tables already exist
        #         try:
        #             for statement in create_tables_query.split(";"):
        #                 if statement.strip():
        #                     db.execute_update(statement, None)
        #         except Exception as e:
        #             # Tables might already exist, that is OK
        #             if "already exists" not in str(e).lower():
        #                 raise e
        
        # Insert into schedule_master and get the ID properly
        master_query = """
            INSERT INTO schedule_master (week_start_date, status, created_by)
            VALUES (%s, 'draft', 'Lieu')
        """
        
        # Execute insert
        db.execute_update(master_query, (week_start,))
        
        # Get the last inserted id using a separate connection
        # Get the last inserted id
        last_id_query = "SELECT LAST_INSERT_ID() as id"
        result = db.execute_query(last_id_query)
        schedule_id = result[0]["id"] if result else None
        
        if not schedule_id:
            raise Exception("Failed to get schedule ID")
        
        print(f"Got schedule_id: {schedule_id}")
        # Insert schedule details
        for employee_schedule in schedule_data:
            try:
                print(f"Saving employee: {employee_schedule}")
                detail_query = """
                    INSERT INTO schedule_details 
                    (schedule_id, employee_name, monday_time, tuesday_time, 
                     wednesday_time, thursday_time, friday_time, saturday_time, sunday_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                times = employee_schedule["times"]
                # Pad times list to 7 days if needed
                while len(times) < 7:
                    times.append("OFF")
                    
                db.execute_update(detail_query, (
                    schedule_id,
                    employee_schedule["employee"],
                    times[0], times[1], times[2], times[3], 
                    times[4], times[5], times[6]
                ))
            except Exception as detail_error:
                print(f"Error saving detail: {detail_error}")
                continue
        
        return jsonify({
            'success': True,
            'schedule_id': schedule_id,
            'message': f'Schedule saved successfully with ID {schedule_id}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schedule_bp.route('/api/schedule/employees', methods=['GET'])
def get_employees():
    try:
        query = "SELECT id, name FROM employees WHERE is_active = 1 ORDER BY name"
        employees = db.fetch_all(query)
        return jsonify({
            'success': True,
            'employees': employees
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schedule_bp.route('/api/schedule/weekly', methods=['GET'])
def get_weekly_schedule():
    """Get weekly schedule data"""
    return jsonify({
        'success': True,
        'schedule': {
            'week_start': '2025-08-12',
            'employees': [],
            'message': 'No schedule data yet'
        }
    })

@schedule_bp.route('/api/schedule/load/<week_date>', methods=['GET'])
def load_schedule(week_date):
    try:
        query = """
            SELECT sm.*, sd.*
            FROM schedule_master sm
            JOIN schedule_details sd ON sm.id = sd.schedule_id
            WHERE sm.week_start_date = %s
            ORDER BY sd.id
        """
        results = db.fetch_all(query, (week_date,))
        
        return jsonify({
            'success': True,
            'schedule': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schedule_bp.route('/api/schedule/predictions/weekly', methods=['GET'])
def get_weekly_predictions():
    """Get real predictions from database"""
    try:
        query = """
            SELECT 
                prediction_date,
                predicted_orders,
                confidence_score,
                DAYNAME(prediction_date) as day_name
            FROM order_predictions
            WHERE prediction_date >= CURDATE()
            ORDER BY prediction_date
            LIMIT 7
        """
        
        results = db.execute_query(query)
        
        predictions = {}
        total = 0
        
        for row in results:
            date_str = row['prediction_date'].strftime('%Y-%m-%d')
            predictions[date_str] = {
                'date': date_str,
                'day_name': row['day_name'],
                'predicted_orders': row['predicted_orders'],
                'confidence': row['confidence_score']
            }
            total += row['predicted_orders']
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'total_predicted': total,
            'daily_average': total // 7 if results else 0
        })
        
    except Exception as e:
        print(f"Error getting predictions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@schedule_bp.route('/api/schedule/employees/all', methods=['GET'])
def get_all_employees():
    """Get all active employees with their best performance stations"""
    try:
        query = """
            SELECT DISTINCT
                e.id,
                e.name,
                COALESCE(
                    (SELECT al.activity_type 
                     FROM activity_logs al 
                     WHERE al.employee_id = e.id 
                       AND al.window_start >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                     GROUP BY al.activity_type 
                     ORDER BY SUM(al.items_count) DESC 
                     LIMIT 1), 
                    'No Activity'
                ) as best_station,
                COALESCE(
                    (SELECT ROUND(AVG(al.items_count / GREATEST(al.duration_minutes/60, 0.1)), 0)
                     FROM activity_logs al 
                     WHERE al.employee_id = e.id 
                       AND al.window_start >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)),
                    0
                ) as items_per_hour
            FROM employees e
            WHERE e.is_active = 1
            ORDER BY e.name
        """
        
        results = db.execute_query(query)
        
        employees = []
        for row in results:
            employees.append({
                'id': row['id'],
                'name': row['name'],
                'best_station': row['best_station'],
                'performance': f"{int(row['items_per_hour'])} items/hr"
            })
        
        return jsonify({
            'success': True,
            'employees': employees,
            'total': len(employees)
        })
        
    except Exception as e:
        print(f"Error getting employees: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
