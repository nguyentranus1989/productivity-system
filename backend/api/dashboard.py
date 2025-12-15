import os
# backend/api/dashboard.py
from database.db_manager import DatabaseManager, get_db
from flask import Blueprint, jsonify, request
from utils.timezone_helpers import TimezoneHelper

# Redis-backed cache with in-memory fallback
import time
import json as json_module
import logging

_endpoint_cache = {}  # In-memory fallback
_redis_cache = None  # Lazy-loaded Redis client

def clear_dashboard_cache():
    """Clear all dashboard caches (called after data recalculation)."""
    global _endpoint_cache
    _endpoint_cache.clear()

    # Also clear Redis cache if available
    redis = _get_redis_cache()
    if redis:
        try:
            redis.delete_pattern("dashboard:*")
        except Exception:
            pass  # Redis pattern delete may not be available

def _get_redis_cache():
    """Lazy-load Redis cache manager"""
    global _redis_cache
    if _redis_cache is None:
        try:
            from database.cache_manager import get_cache_manager
            _redis_cache = get_cache_manager()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Redis unavailable, using in-memory cache: {e}")
            _redis_cache = False  # Mark as unavailable
    return _redis_cache if _redis_cache else None

def cached_endpoint(ttl_seconds=10):
    """Cache decorator - uses Redis with in-memory fallback"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            from flask import request
            cache_key = f"dashboard:{func.__name__}:{request.full_path}"
            logger = logging.getLogger(__name__)

            # Try Redis first
            redis = _get_redis_cache()
            if redis:
                try:
                    cached = redis.get(cache_key)
                    if cached:
                        logger.debug(f"Redis HIT: {cache_key}")
                        return jsonify(json_module.loads(cached))
                except Exception as e:
                    logger.warning(f"Redis get error: {e}")

            # Fallback: check in-memory cache
            if cache_key in _endpoint_cache:
                data, timestamp = _endpoint_cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    logger.debug(f"Memory HIT: {cache_key}")
                    return data

            # Cache miss - execute function
            result = func(*args, **kwargs)

            # Store in Redis if available
            if redis:
                try:
                    # Extract JSON data from Flask response
                    if hasattr(result, 'get_json'):
                        json_data = result.get_json()
                    else:
                        json_data = result
                    redis.set(cache_key, json_module.dumps(json_data), ttl=ttl_seconds)
                    logger.debug(f"Redis SET: {cache_key} (TTL: {ttl_seconds}s)")
                except Exception as e:
                    logger.warning(f"Redis set error: {e}")

            # Also store in memory as backup
            _endpoint_cache[cache_key] = (result, time.time())

            # Clean old in-memory entries periodically
            if len(_endpoint_cache) > 100:
                current_time = time.time()
                keys_to_delete = [k for k, (_, ts) in _endpoint_cache.items()
                                  if current_time - ts > ttl_seconds * 2]
                for k in keys_to_delete:
                    del _endpoint_cache[k]

            return result
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

from datetime import datetime, timedelta
import mysql.connector
from functools import wraps
import pytz
import logging

from dotenv import load_dotenv
load_dotenv()

# Create logger
logger = logging.getLogger(__name__)

# Initialize timezone helper
tz_helper = TimezoneHelper()

ACTION_TO_DEPARTMENT_MAP = {
    'In Production': 'Heat Press',
    'Picking': 'Picking',
    'Labeling': 'Labeling',
    'Film Matching': 'Packing',
    'QC Passed': 'Packing'
}

PODFACTORY_ROLE_TO_CONFIG_ID = {
    'Heat Pressing': 1,
    'Packing and Shipping': 2,
    'Picker': 3,
    'Labeler': 4,
    'Film Matching': 5
}

# Map PodFactory actions to role_configs.id
ACTION_TO_ROLE_ID = {
    'In Production': 1,      # Heat Pressing
    'QC Passed': 2,          # Packing and Shipping  
    'Picking': 3,            # Picker
    'Labeling': 4,           # Labeler
    'Film Matching': 5       # Film Matching
}

dashboard_bp = Blueprint('dashboard', __name__)

# Database connection configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'productivity_tracker')
}

def get_central_date():
    """Get current date in Central Time"""
    central = pytz.timezone('America/Chicago')
    return datetime.now(central).date()

def get_central_datetime():
    """Get current datetime in Central Time"""
    central = pytz.timezone('America/Chicago')
    return datetime.now(central)

# Database connection function
def get_db_connection():
    """Create and return a database connection"""
    return mysql.connector.connect(**DB_CONFIG)

# API key decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != 'dev-api-key-123':
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Department Statistics
@dashboard_bp.route('/departments/stats', methods=['GET'])
@require_api_key
@cached_endpoint(ttl_seconds=60)  # 1 min TTL for Redis caching benefit
def get_department_stats():
    
    """Get performance statistics by department based on actual activities"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Use dynamic date
        date = request.args.get('date', get_central_date().strftime('%Y-%m-%d'))
        
        # Get department stats with proper efficiency calculation
        # Formula: total_items / total_hours / target_per_hour
        # Step 1: Get items per employee per department
        # Step 2: Join with clock_hours (one row per employee)
        # Step 3: Aggregate by department
        query = """
        SELECT
            dept_emp.department as department_name,
            COUNT(*) as employee_count,
            SUM(dept_emp.emp_items) as total_items,
            COALESCE(SUM(ct.clock_hours), 0) as total_hours,
            COUNT(CASE WHEN ct.clock_hours > 0 THEN 1 END) as clocked_employees
        FROM (
            SELECT
                department,
                employee_id,
                SUM(items_count) as emp_items
            FROM activity_logs
            WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = %s
            AND source = 'podfactory'
            GROUP BY department, employee_id
        ) dept_emp
        LEFT JOIN (
            SELECT
                employee_id,
                SUM(total_minutes) / 60.0 as clock_hours
            FROM clock_times
            WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
            GROUP BY employee_id
        ) ct ON ct.employee_id = dept_emp.employee_id
        GROUP BY dept_emp.department
        HAVING total_items > 0
        """

        cursor.execute(query, (date, date))
        departments = cursor.fetchall()
        
        # Create a dict to check existing departments
        existing_depts = {d['department_name']: d for d in departments}
        
        # Add standard departments if missing
        standard_depts = ['Picking', 'Packing', 'Heat Press', 'Labeling']
        
        for dept_name in standard_depts:
            if dept_name not in existing_depts:
                departments.append({
                    'department_name': dept_name,
                    'employee_count': 0,
                    'total_items': 0,
                    'avg_items_per_minute': 0,
                    'avg_efficiency': 0
                })
        
        # Add performance vs target - fetch from role_configs (single source of truth)
        cursor.execute("SELECT role_name, expected_per_hour FROM role_configs")
        role_targets = {row['role_name']: float(row['expected_per_hour']) for row in cursor.fetchall()}

        # Map department names to role names
        dept_to_role = {
            'Heat Press': 'Heat Pressing',
            'Packing': 'Packing and Shipping',
            'Picking': 'Picker',
            'Labeling': 'Labeler',
            'Film Matching': 'Film Matching'
        }

        for dept in departments:
            dept_name = dept['department_name']
            role_name = dept_to_role.get(dept_name, dept_name)
            expected_per_hour = role_targets.get(role_name, 60.0)  # Default 60/hr if not found

            total_items = int(dept.get('total_items', 0))
            total_hours = float(dept.get('total_hours', 0) or 0)
            employee_count = int(dept.get('employee_count', 0) or 1)
            clocked_employees = int(dept.get('clocked_employees', 0))
            unclocked_employees = employee_count - clocked_employees

            # Estimate hours for employees without clock times (use avg of clocked employees)
            if clocked_employees > 0 and unclocked_employees > 0:
                avg_hours_per_employee = total_hours / clocked_employees
                estimated_hours = total_hours + (unclocked_employees * avg_hours_per_employee)
            else:
                estimated_hours = total_hours if total_hours > 0 else employee_count * 8  # Fallback 8hr

            # Calculate items per hour (per hour of labor)
            items_per_hour = total_items / estimated_hours if estimated_hours > 0 else 0

            # Efficiency = actual items/hr / target items/hr × 100
            dept['efficiency'] = round((items_per_hour / expected_per_hour) * 100, 1) if expected_per_hour > 0 else 0
            dept['vs_target'] = round(dept['efficiency'] - 100, 1)
            dept['target_rate'] = round(expected_per_hour / 60, 2)  # Per person per min (for display)
            dept['avg_rate'] = round(items_per_hour / 60, 2)  # Items per minute (for display)
            dept['avg_items_per_minute'] = dept['avg_rate']  # Alias for frontend
            dept['name'] = dept_name
            dept['total_items'] = total_items
            dept['employee_count'] = employee_count
        
        cursor.close()
        conn.close()
        
        return jsonify(departments)
        
    except Exception as e:
        import traceback
        print(f"Error in department stats: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/departments/targets', methods=['GET'])
@require_api_key
def get_department_targets():
    """Get all department target rates"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT department_name, target_rate_per_person, updated_at FROM department_targets ORDER BY department_name")
        targets = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(targets)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/departments/targets/<dept_name>', methods=['PUT'])
@require_api_key
def update_department_target(dept_name):
    """Update target rate for a department"""
    try:
        data = request.get_json()
        new_rate = float(data.get('target_rate_per_person', 15.0))

        if new_rate <= 0:
            return jsonify({'error': 'Target rate must be greater than 0'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Upsert - insert if not exists, update if exists
        cursor.execute("""
            INSERT INTO department_targets (department_name, target_rate_per_person)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE target_rate_per_person = VALUES(target_rate_per_person)
        """, (dept_name, new_rate))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'department_name': dept_name,
            'target_rate_per_person': new_rate
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Replace the get_leaderboard function in dashboard.py with this updated version:

@dashboard_bp.route('/leaderboard', methods=['GET'])
@require_api_key
@cached_endpoint(ttl_seconds=30)  # 30s TTL for Redis caching benefit
def get_leaderboard():
    """Get employee leaderboard with comprehensive data"""
    date = request.args.get('date', get_central_date().strftime('%Y-%m-%d'))
    
    # Get UTC boundaries from request
    utc_start = request.args.get('utc_start')
    utc_end = request.args.get('utc_end')
    
    # If UTC boundaries not provided, calculate them (fallback for backwards compatibility)
    if not utc_start or not utc_end:
        year, month, day = map(int, date.split('-'))
        # Simple DST check (CDT runs March - November)
        is_dst = 3 <= month <= 11
        offset_hours = 5 if is_dst else 6
        
        # Calculate UTC boundaries
        utc_start = f"{date} {offset_hours:02d}:00:00"
        
        # Next day for end boundary
        from datetime import datetime, timedelta
        next_day = datetime(year, month, day) + timedelta(days=1)
        utc_end = f"{next_day.strftime('%Y-%m-%d')} {offset_hours-1:02d}:59:59"
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Updated query using UTC boundaries
        query = """
        WITH activity_aggregates AS (
            -- Aggregate items by employee and activity type using UTC boundaries
            SELECT 
                al.employee_id,
                al.activity_type,
                SUM(al.items_count) as total_items
            FROM activity_logs al
            WHERE al.window_start >= %s AND al.window_start <= %s
            AND al.source = 'podfactory'
            GROUP BY al.employee_id, al.activity_type
            HAVING total_items > 0
        )
        SELECT
            e.id,
            e.name,
            COALESCE(ds.items_processed, 0) as items_today,
            COALESCE(ds.points_earned, 0) as score,
            COALESCE(ds.active_minutes, 0) as active_minutes,
            e.current_streak as streak,
            ct.total_minutes,
            ct.is_clocked_in,
            -- Activity breakdown for display
            (
                SELECT GROUP_CONCAT(
                    CONCAT(
                        CASE 
                            WHEN activity_type = 'Picking' THEN '🎯 '
                            WHEN activity_type = 'Labeling' THEN '🏷️ '
                            WHEN activity_type = 'Film Matching' THEN '🎬 '
                            WHEN activity_type = 'In Production' THEN '🔥 '
                            WHEN activity_type = 'QC Passed' THEN '📦 '
                            ELSE ''
                        END,
                        CASE 
                            WHEN activity_type = 'QC Passed' THEN 'Shipping'
                            WHEN activity_type = 'In Production' THEN 'Heat Pressing'
                            ELSE activity_type
                        END,
                        ': ',
                        total_items
                    )
                    ORDER BY 
                        CASE activity_type
                            WHEN 'Picking' THEN 1
                            WHEN 'Labeling' THEN 2
                            WHEN 'Film Matching' THEN 3
                            WHEN 'In Production' THEN 4
                            WHEN 'QC Passed' THEN 5
                            ELSE 6
                        END
                    SEPARATOR ' - '
                )
                FROM activity_aggregates aa
                WHERE aa.employee_id = e.id
            ) as activity_breakdown,
            -- Get primary role based on most items using UTC boundaries
            (
                SELECT rc.role_name
                FROM activity_logs al2
                JOIN role_configs rc ON rc.id = al2.role_id
                WHERE al2.employee_id = e.id
                AND al2.window_start >= %s AND al2.window_start <= %s
                GROUP BY al2.role_id, rc.role_name
                ORDER BY SUM(al2.items_count) DESC
                LIMIT 1
            ) as primary_department
        FROM employees e
        LEFT JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = %s
        LEFT JOIN (
            -- Clock times: calculate real-time minutes (not stored value)
            -- Only include today's shifts in CT timezone
            SELECT
                employee_id,
                SUM(GREATEST(0, TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, UTC_TIMESTAMP())))) as total_minutes,
                MAX(CASE WHEN clock_out IS NULL THEN 1 ELSE 0 END) as is_clocked_in
            FROM clock_times
            WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
            GROUP BY employee_id
        ) ct ON ct.employee_id = e.id
        WHERE e.is_active = 1
        AND (ct.employee_id IS NOT NULL OR ds.items_processed > 0)
        ORDER BY COALESCE(ds.points_earned, 0) DESC
        """
        
        # Execute: activity_aggregates(utc_start, utc_end), primary_dept(utc_start, utc_end), daily_scores(date), clock_times(date)
        cursor.execute(query, (utc_start, utc_end, utc_start, utc_end, date, date))
        leaderboard = cursor.fetchall()
        
        # Process and format the data (rest remains the same)
        for idx, emp in enumerate(leaderboard):
            emp['rank'] = idx + 1
            emp['score'] = round(float(emp['score'] or 0), 2)
            emp['items_today'] = int(emp['items_today'] or 0)
            emp['department'] = emp['primary_department'] or 'No Activity'
            
            # Format time worked properly
            total_mins = int(emp.get('total_minutes', 0) or 0)
            
            hours = total_mins // 60
            minutes = total_mins % 60
            emp['time_worked'] = f"{hours}:{minutes:02d}"
            
            # Calculate items per minute correctly
            if total_mins > 0:
                emp['items_per_minute'] = round(emp['items_today'] / total_mins, 1)
                emp['items_per_hour'] = round((emp['items_today'] / total_mins) * 60, 1)
            else:
                emp['items_per_minute'] = 0
                emp['items_per_hour'] = 0
                
            # Set the activity breakdown for display
            emp['activity_display'] = emp['activity_breakdown'] or 'No activities'
            
            # Calculate progress bar (daily goal based on hours worked)
            hours_worked = total_mins / 60 if total_mins > 0 else 0
            daily_goal = hours_worked * 50 if hours_worked > 0 else 400
            emp['progress'] = min(100, (emp['items_today'] / daily_goal) * 100) if daily_goal > 0 else 0
            
            # Department icon
            dept_icons = {
                'Picker': '🎯',
                'Packing and Shipping': '📦',
                'Heat Pressing': '🔥',
                'Labeler': '🏷️',
                'Film Matching': '🎬',
                'No Activity': '💤'
            }
            emp['department_icon'] = dept_icons.get(emp['department'], '📋')
            
            # Clock status
            emp['clock_status'] = '🟢' if emp['is_clocked_in'] else '🔴'
            emp['status_text'] = 'Active' if emp['is_clocked_in'] else 'Off'
            
            # Badges based on performance
            if emp['score'] >= 200:
                emp['badge'] = '🔥 Top Performer!'
            elif emp['score'] >= 100:
                emp['badge'] = '⭐ Star Player'
            elif emp['streak'] and emp['streak'] >= 5:
                emp['badge'] = f"🔥 {emp['streak']}-day streak!"
            elif emp['items_per_minute'] and emp['items_per_minute'] >= 1:
                emp['badge'] = "⚡ Speed Demon"
            else:
                emp['badge'] = "🌟 Team Player"
        
        cursor.close()
        conn.close()
        
        return jsonify(leaderboard)
        
    except Exception as e:
        import traceback
        print(f"Error in leaderboard: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    
# Add this new endpoint for date range analytics
@dashboard_bp.route('/analytics/date-range', methods=['GET'])
@require_api_key
def get_date_range_stats():
    """Get aggregated statistics for a date range"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Both start_date and end_date are required'}), 400
        
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if start > end:
            return jsonify({'error': 'start_date must be before end_date'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get aggregated employee data - FIXED: removed e.department
        query = """
            SELECT 
                e.id,
                e.name,
                COUNT(DISTINCT ds.score_date) as days_worked,
                COALESCE(SUM(ds.items_processed), 0) as total_items,
                COALESCE(SUM(ds.points_earned), 0) as total_points,
                COALESCE(AVG(CASE WHEN ds.items_processed > 0 THEN ds.items_processed END), 0) as avg_daily_items,
                COALESCE(MAX(ds.items_processed), 0) as best_day_items,
                COALESCE(MIN(CASE WHEN ds.items_processed > 0 THEN ds.items_processed END), 0) as worst_day_items,
                -- Get most common department from activity logs
                (
                    SELECT al.department 
                    FROM activity_logs al 
                    WHERE al.employee_id = e.id 
                    AND DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
                    GROUP BY al.department 
                    ORDER BY COUNT(*) DESC 
                    LIMIT 1
                ) as department
            FROM employees e
            LEFT JOIN daily_scores ds ON ds.employee_id = e.id 
                AND ds.score_date BETWEEN %s AND %s
            WHERE e.is_active = 1
            GROUP BY e.id, e.name
            ORDER BY total_points DESC
        """
        
        cursor.execute(query, (start, end, start, end))
        results = cursor.fetchall()
        
        # Format results
        leaderboard = []
        for row in results:
            try:
                # Safe consistency calculation
                best = float(row['best_day_items'] or 0)
                worst = float(row['worst_day_items'] or 0)
                avg = float(row['avg_daily_items'] or 0)
                total_items = int(row['total_items'] or 0)
                
                # Only include employees who have worked
                if total_items > 0:
                    if avg > 0 and best > worst:
                        # Calculate consistency (100% = perfectly consistent)
                        variance = best - worst
                        consistency = max(0, min(100, 100 - (variance / avg * 50)))
                    else:
                        consistency = 100 if total_items > 0 else 0
                    
                    leaderboard.append({
                        'id': row['id'],
                        'name': row['name'],
                        'department': row['department'] or 'Unknown',
                        'days_worked': int(row['days_worked'] or 0),
                        'total_items': total_items,
                        'total_points': round(float(row['total_points'] or 0), 1),
                        'avg_daily_items': round(avg, 1),
                        'best_day': int(best),
                        'worst_day': int(worst),
                        'consistency': round(consistency, 1)
                    })
            except Exception as e:
                logger.error(f"Error processing employee {row.get('name', 'Unknown')}: {str(e)}")
                continue
        
        # Get department summary
        dept_query = """
            SELECT 
                COALESCE(al.department, 'Unknown') as department,
                COUNT(DISTINCT DATE(al.window_start)) as active_days,
                COUNT(DISTINCT al.employee_id) as unique_employees,
                COALESCE(SUM(al.items_count), 0) as total_items,
                COALESCE(AVG(al.items_count), 0) as avg_items_per_activity
            FROM activity_logs al
            WHERE DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
                AND al.source = 'podfactory'
            GROUP BY al.department
            HAVING total_items > 0
        """
        
        cursor.execute(dept_query, (start, end))
        dept_results = cursor.fetchall()
        
        # Format department results
        departments = []
        for dept in dept_results:
            try:
                departments.append({
                    'department': dept['department'],
                    'active_days': int(dept['active_days'] or 0),
                    'unique_employees': int(dept['unique_employees'] or 0),
                    'total_items': int(dept['total_items'] or 0),
                    'avg_items_per_activity': round(float(dept['avg_items_per_activity'] or 0), 1)
                })
            except Exception as e:
                logger.error(f"Error processing department {dept.get('department', 'Unknown')}: {str(e)}")
                continue
        
        # Get range summary stats (avg employees/day, total items, efficiency)
        summary_query = """
            SELECT
                COUNT(DISTINCT ds.employee_id) as total_employees,
                SUM(ds.clocked_minutes) as total_clocked_minutes,
                SUM(ds.active_minutes) as total_active_minutes,
                SUM(ds.items_processed) as total_items,
                COUNT(DISTINCT ds.score_date) as days_with_data
            FROM daily_scores ds
            WHERE ds.score_date BETWEEN %s AND %s
        """
        cursor.execute(summary_query, (start, end))
        summary = cursor.fetchone()

        # Get avg employees per day (employees who clocked in each day)
        avg_emp_query = """
            SELECT AVG(daily_count) as avg_employees_per_day
            FROM (
                SELECT ds.score_date, COUNT(DISTINCT ds.employee_id) as daily_count
                FROM daily_scores ds
                WHERE ds.score_date BETWEEN %s AND %s
                  AND ds.clocked_minutes > 0
                GROUP BY ds.score_date
            ) daily_counts
        """
        cursor.execute(avg_emp_query, (start, end))
        avg_emp_result = cursor.fetchone()

        # Get QC Passed items only (not all activity types)
        qc_items_query = """
            SELECT SUM(al.items_count) as qc_items
            FROM activity_logs al
            WHERE DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
              AND al.activity_type = 'QC Passed'
        """
        cursor.execute(qc_items_query, (start, end))
        qc_result = cursor.fetchone()
        qc_items = int(qc_result['qc_items'] or 0)

        total_clocked = float(summary['total_clocked_minutes'] or 0)
        total_active = float(summary['total_active_minutes'] or 0)
        avg_efficiency = round((total_active / total_clocked * 100), 1) if total_clocked > 0 else 0

        cursor.close()
        conn.close()

        total_days = (end - start).days + 1
        total_items = qc_items  # QC Passed items only
        total_employees = int(summary['total_employees'] or 0)
        avg_employees_per_day = round(float(avg_emp_result['avg_employees_per_day'] or 0), 1)

        return jsonify({
            'date_range': {
                'start': start_date,
                'end': end_date,
                'days': total_days
            },
            'leaderboard': leaderboard,
            'department_summary': departments,
            'summary': {
                'total_employees': total_employees,
                'avg_employees_per_day': avg_employees_per_day,
                'total_items': total_items,
                'avg_items_per_day': round(total_items / total_days, 0) if total_days > 0 else 0,
                'avg_efficiency': avg_efficiency,
                'total_clocked_hours': round(total_clocked / 60, 1),
                'total_active_hours': round(total_active / 60, 1)
            },
            'total_employees': len(leaderboard),
            'generated_at': datetime.now().isoformat()
        })

    except Exception as e:
        import traceback
        logger.error(f"Error getting date range stats: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': 'Failed to get date range statistics', 'details': str(e)}), 500
    
# Add this new endpoint to dashboard.py after line 830 (after get_active_alerts)
@dashboard_bp.route('/clock-times/today', methods=['GET'])
@require_api_key
def get_today_clock_times():
    """Get all clock in/out times for today"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get today's date in CT for joins
        today_ct = get_central_date().strftime('%Y-%m-%d')

        # Get all clock times for today with active minutes from daily_scores
        cursor.execute("""
            SELECT
                ct.id,
                e.name as employee_name,
                ct.clock_in,
                ct.clock_out,
                CASE WHEN ct.clock_out IS NULL THEN 1 ELSE 0 END as is_clocked_in,
                GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, IFNULL(ct.clock_out, UTC_TIMESTAMP()))) as total_minutes,
                COALESCE(ds.active_minutes, 0) as active_minutes,
                COALESCE(ds.items_processed, 0) as items_processed
            FROM clock_times ct
            JOIN employees e ON e.id = ct.employee_id
            LEFT JOIN daily_scores ds ON ds.employee_id = ct.employee_id AND ds.score_date = %s
            WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
            ORDER BY ct.clock_in DESC
        """, (today_ct, today_ct))
        
        clock_times = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify(clock_times)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@dashboard_bp.route('/server-time', methods=['GET'])
@require_api_key
def get_server_time():
    """Get current server time in various timezones"""
    utc_now = datetime.utcnow()
    central = pytz.timezone('America/Chicago')
    central_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(central)
    
    return jsonify({
        'utc': utc_now.isoformat(),
        'central': central_now.isoformat(),
        'central_date': central_now.date().isoformat(),
        'central_time': central_now.strftime('%I:%M:%S %p'),
        'day_of_week': central_now.strftime('%A')
    })

# Enhanced Live Leaderboard
@dashboard_bp.route('/leaderboard/live', methods=['GET'])
@require_api_key
def get_live_leaderboard():
    """Enhanced leaderboard with position changes and badges"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)
        yesterday_ct = ct_date - timedelta(days=1)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get current rankings with position changes
        cursor.execute("""
            WITH current_ranks AS (
                SELECT
                    e.id,
                    e.name,
                    ds.items_processed,
                    ds.points_earned,
                    ROUND(ct.hours_worked, 1) as hours_worked,
                    e.current_streak,
                    ROW_NUMBER() OVER (ORDER BY ds.points_earned DESC) as current_rank,
                    LAG(ds.points_earned, 1) OVER (ORDER BY ds.points_earned DESC) as prev_points,
                    -- Calculate items per minute based on clock time
                    CASE
                        WHEN ct.clock_minutes > 0 THEN ROUND(ds.items_processed / ct.clock_minutes * 60, 1)
                        ELSE 0
                    END as items_per_minute
                FROM daily_scores ds
                JOIN employees e ON e.id = ds.employee_id
                LEFT JOIN (
                    SELECT
                        employee_id,
                        -- Calculate actual worked time without duplicates (UTC comparison)
                        ROUND(
                            TIMESTAMPDIFF(MINUTE,
                                MIN(clock_in),
                                COALESCE(MAX(clock_out), UTC_TIMESTAMP())
                            ) / 60.0,
                            1
                        ) as hours_worked,
                        TIMESTAMPDIFF(MINUTE,
                            MIN(clock_in),
                            COALESCE(MAX(clock_out), UTC_TIMESTAMP())
                        ) as clock_minutes
                    FROM clock_times
                    WHERE clock_in >= %s AND clock_in < %s
                    GROUP BY employee_id
                ) ct ON ct.employee_id = e.id
                WHERE ds.score_date = %s
                AND ds.points_earned > 0
            ),
            yesterday_ranks AS (
                SELECT
                    employee_id,
                    ROW_NUMBER() OVER (ORDER BY points_earned DESC) as yesterday_rank
                FROM daily_scores
                WHERE score_date = %s
            )
            SELECT
                cr.*,
                COALESCE(yr.yesterday_rank, 999) as yesterday_rank,
                CASE
                    WHEN yr.yesterday_rank IS NULL THEN 'new'
                    WHEN cr.current_rank < yr.yesterday_rank THEN 'up'
                    WHEN cr.current_rank > yr.yesterday_rank THEN 'down'
                    ELSE 'same'
                END as movement,
                ABS(COALESCE(yr.yesterday_rank, cr.current_rank) - cr.current_rank) as positions_moved
            FROM current_ranks cr
            LEFT JOIN yesterday_ranks yr ON yr.employee_id = cr.id
            ORDER BY cr.current_rank
            LIMIT 10
        """, (utc_start, utc_end, ct_date, yesterday_ct))
        
        leaderboard = cursor.fetchall()
        
        # Add badges and enhancements
        for emp in leaderboard:
            # Rank display
            if emp['current_rank'] == 1:
                emp['rank_display'] = "🥇"
                emp['badge'] = "👑 Champion"
            elif emp['current_rank'] == 2:
                emp['rank_display'] = "🥈"
                emp['badge'] = "⚡ Lightning Fast"
            elif emp['current_rank'] == 3:
                emp['rank_display'] = "🥉"
                emp['badge'] = "🌟 Rising Star"
            else:
                emp['rank_display'] = f"#{emp['current_rank']}"
                
                # Dynamic badges
                if emp['current_streak'] and emp['current_streak'] >= 5:
                    emp['badge'] = f"🔥 {emp['current_streak']}-day streak!"
                elif emp['movement'] == 'up':
                    emp['badge'] = f"📈 Up {emp['positions_moved']} spots!"
                elif emp['items_processed'] >= 500:
                    emp['badge'] = "💪 Powerhouse"
                elif emp['hours_worked'] and emp['items_per_minute'] and emp['items_per_minute'] > 20:
                    emp['badge'] = "⚡ Speed Demon"
                else:
                    emp['badge'] = "💯 Team Player"
            
            # Movement indicator
            if emp['movement'] == 'up':
                emp['movement_icon'] = f"↑{emp['positions_moved']}"
                emp['movement_color'] = "green"
            elif emp['movement'] == 'down':
                emp['movement_icon'] = f"↓{emp['positions_moved']}"
                emp['movement_color'] = "red"
            elif emp['movement'] == 'new':
                emp['movement_icon'] = "NEW"
                emp['movement_color'] = "blue"
            else:
                emp['movement_icon'] = "-"
                emp['movement_color'] = "gray"
            
            # Progress to next milestone
            milestones = [100, 250, 500, 750, 1000, 1500, 2000]
            current_points = float(emp['points_earned'])
            next_milestone = next((m for m in milestones if m > current_points), milestones[-1])
            emp['next_milestone'] = next_milestone
            emp['milestone_progress'] = min(100, (current_points / next_milestone) * 100)
        
        cursor.close()
        conn.close()
        
        return jsonify(leaderboard)
        
    except Exception as e:
        import traceback
        print(f"Error in live leaderboard: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# Streak Leaders
@dashboard_bp.route('/analytics/streak-leaders', methods=['GET'])
@require_api_key
def get_streak_leaders():
    """Get top employees by current streak"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get top 5 employees with longest streaks
        cursor.execute("""
            SELECT
                e.id,
                e.name,
                e.current_streak as streak_days,
                ds.items_processed as items_today,
                ds.points_earned as points_today,
                -- Get most recent department
                (
                    SELECT al.department
                    FROM activity_logs al
                    WHERE al.employee_id = e.id
                    AND al.window_start >= %s AND al.window_start < %s
                    ORDER BY al.window_start DESC
                    LIMIT 1
                ) as department
            FROM employees e
            LEFT JOIN daily_scores ds ON ds.employee_id = e.id
                AND ds.score_date = %s
            WHERE e.is_active = 1
            AND e.current_streak > 0
            ORDER BY e.current_streak DESC, ds.points_earned DESC
            LIMIT 5
        """, (utc_start, utc_end, ct_date))
        
        streak_leaders = cursor.fetchall()
        
        # Format the response
        leaders = []
        for leader in streak_leaders:
            leaders.append({
                'id': leader['id'],
                'name': leader['name'],
                'streak_days': leader['streak_days'] or 0,
                'items_today': leader['items_today'] or 0,
                'points_today': float(leader['points_today'] or 0),
                'department': leader['department'] or 'Unknown'
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(leaders)
        
    except Exception as e:
        import traceback
        print(f"Error getting streak leaders: {str(e)}")
        print(traceback.format_exc())
        return jsonify([])

# Achievement Ticker
@dashboard_bp.route('/analytics/achievement-ticker', methods=['GET'])
@require_api_key
def get_achievement_ticker():
    """Get achievements and milestones for the ticker"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        achievements = []

        # 1. Top performer of the day
        cursor.execute("""
            SELECT
                e.name,
                ds.points_earned,
                ds.items_processed
            FROM daily_scores ds
            JOIN employees e ON e.id = ds.employee_id
            WHERE ds.score_date = %s
            ORDER BY ds.points_earned DESC
            LIMIT 1
        """, (ct_date,))

        top_performer = cursor.fetchone()
        if top_performer:
            achievements.append(f"🏆 {top_performer['name']} earned {int(top_performer['points_earned'])} points today!")

        # 2. High speed achievements
        cursor.execute("""
            SELECT
                e.name,
                ROUND(ds.items_processed / GREATEST(ct.clock_minutes, 1) * 60, 0) as items_per_hour
            FROM daily_scores ds
            JOIN employees e ON e.id = ds.employee_id
            LEFT JOIN (
                SELECT
                    employee_id,
                    GREATEST(0, TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), UTC_TIMESTAMP()))) as clock_minutes
                FROM clock_times
                WHERE clock_in >= %s AND clock_in < %s
                GROUP BY employee_id
            ) ct ON ct.employee_id = e.id
            WHERE ds.score_date = %s
            AND ct.clock_minutes > 30
            HAVING items_per_hour >= 50
            ORDER BY items_per_hour DESC
            LIMIT 3
        """, (utc_start, utc_end, ct_date))
        
        speed_demons = cursor.fetchall()
        for emp in speed_demons:
            achievements.append(f"⚡ {emp['name']} hit {int(emp['items_per_hour'])} items/hour!")
        
        # 3. REMOVED DEPARTMENT TOTALS - They were misleading
        
        # 4. Active streaks
        cursor.execute("""
            SELECT 
                e.name,
                e.current_streak
            FROM employees e
            WHERE e.is_active = 1
            AND e.current_streak >= 3
            ORDER BY e.current_streak DESC
            LIMIT 3
        """)
        
        streakers = cursor.fetchall()
        for emp in streakers:
            achievements.append(f"🔥 {emp['name']} on a {emp['current_streak']}-day streak!")
        
        # 5. Team total - CHANGED TO QC PASSED ONLY
        cursor.execute("""
            SELECT
                COALESCE(SUM(al.items_count), 0) as qc_passed_total
            FROM activity_logs al
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.activity_type = 'QC Passed'
            AND al.source = 'podfactory'
        """, (utc_start, utc_end))

        team_stats = cursor.fetchone()
        if team_stats and team_stats['qc_passed_total'] > 0:
            achievements.append(f"📊 Team total: {int(team_stats['qc_passed_total'])} items QC passed today!")

        # 6. Recent milestones
        cursor.execute("""
            SELECT
                e.name,
                ds.items_processed
            FROM daily_scores ds
            JOIN employees e ON e.id = ds.employee_id
            WHERE ds.score_date = %s
            AND (
                ds.items_processed >= 500
                OR ds.items_processed = 100
                OR ds.items_processed = 250
            )
            ORDER BY ds.updated_at DESC
            LIMIT 2
        """, (ct_date,))
        
        milestones = cursor.fetchall()
        for emp in milestones:
            if emp['items_processed'] >= 500:
                achievements.append(f"🌟 {emp['name']} crushed 500+ items today!")
            elif emp['items_processed'] >= 250:
                achievements.append(f"💪 {emp['name']} hit 250 items!")
            else:
                achievements.append(f"🎉 {emp['name']} reached 100 items!")
        
        cursor.close()
        conn.close()
        
        # Ensure we have some content
        if not achievements:
            achievements = [
                "💪 Keep pushing team!",
                "🏆 Every item counts!",
                "🌟 You're doing amazing!"
            ]
        
        return jsonify(achievements)
        
    except Exception as e:
        import traceback
        print(f"Error getting achievement ticker: {str(e)}")
        print(traceback.format_exc())
        return jsonify([
            "💪 Keep pushing team!",
            "🏆 Every item counts!",
            "🌟 You're doing amazing!"
        ])
# Hourly Heatmap
@dashboard_bp.route('/analytics/hourly-heatmap', methods=['GET'])
@require_api_key
def get_hourly_heatmap():
    """Get hourly productivity heatmap data"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                HOUR(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) as hour,
                COUNT(DISTINCT al.employee_id) as active_employees,
                SUM(al.items_count) as items_processed,
                ROUND(SUM(al.items_count * rc.multiplier), 1) as points_earned
            FROM activity_logs al
            JOIN role_configs rc ON rc.id = al.role_id
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.source = 'podfactory'
            GROUP BY HOUR(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago'))
            ORDER BY hour
        """, (utc_start, utc_end))
        
        hourly_data = cursor.fetchall()
        
        # Fill in missing hours
        heatmap = []
        for hour in range(6, 18):  # 6 AM to 5 PM
            data = next((h for h in hourly_data if h['hour'] == hour), None)
            if data:
                intensity = min(100, (data['points_earned'] / 500) * 100)  # Scale to 100
                heatmap.append({
                    'hour': f"{hour}:00",
                    'employees': data['active_employees'],
                    'items': data['items_processed'],
                    'points': data['points_earned'],
                    'intensity': intensity
                })
            else:
                heatmap.append({
                    'hour': f"{hour}:00",
                    'employees': 0,
                    'items': 0,
                    'points': 0,
                    'intensity': 0
                })
        
        cursor.close()
        conn.close()
        
        return jsonify(heatmap)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Gamification Achievements
@dashboard_bp.route('/gamification/achievements', methods=['GET'])
@require_api_key
def get_achievements():
    """Get achievement progress for gamification"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Daily achievements
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN ds.points_earned >= 100 THEN 1 END) as century_club,
                COUNT(CASE WHEN ds.points_earned >= 250 THEN 1 END) as quarter_master,
                COUNT(CASE WHEN ds.points_earned >= 500 THEN 1 END) as half_hero,
                COUNT(CASE WHEN ds.points_earned >= 1000 THEN 1 END) as thousand_thunder,
                MAX(ds.points_earned) as top_score,
                SUM(ds.points_earned) as total_team_points
            FROM daily_scores ds
            WHERE ds.score_date = %s
        """, (ct_date,))
        
        achievements = cursor.fetchone()
        
        # Add percentages and goals
        total_employees = 33  # Adjust based on your active employees
        
        achievements_list = [
            {
                'name': 'Century Club',
                'description': '100+ points in a day',
                'count': achievements['century_club'] or 0,
                'percentage': ((achievements['century_club'] or 0) / total_employees) * 100,
                'icon': '💯'
            },
            {
                'name': 'Quarter Master',
                'description': '250+ points in a day',
                'count': achievements['quarter_master'] or 0,
                'percentage': ((achievements['quarter_master'] or 0) / total_employees) * 100,
                'icon': '🎯'
            },
            {
                'name': 'Half Hero',
                'description': '500+ points in a day',
                'count': achievements['half_hero'] or 0,
                'percentage': ((achievements['half_hero'] or 0) / total_employees) * 100,
                'icon': '🦸'
            },
            {
                'name': 'Thousand Thunder',
                'description': '1000+ points in a day',
                'count': achievements['thousand_thunder'] or 0,
                'percentage': ((achievements['thousand_thunder'] or 0) / total_employees) * 100,
                'icon': '⚡'
            }
        ]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'achievements': achievements_list,
            'top_score': float(achievements['top_score'] or 0),
            'total_team_points': float(achievements['total_team_points'] or 0),
            'team_goal': 10000,  # Adjust based on your targets
            'team_progress': (float(achievements['total_team_points'] or 0) / 10000) * 100
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Department Battle
@dashboard_bp.route('/departments/battle', methods=['GET'])
@require_api_key
def get_department_battle():
    """Get department vs department competition data"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                al.department,
                COUNT(DISTINCT al.employee_id) as employees,
                SUM(al.items_count) as items,
                ROUND(SUM(al.items_count * rc.multiplier), 1) as points,
                ROUND(AVG(al.items_count * rc.multiplier), 1) as avg_points_per_activity
            FROM activity_logs al
            JOIN role_configs rc ON rc.id = al.role_id
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.source = 'podfactory'
            GROUP BY al.department
            ORDER BY points DESC
        """, (utc_start, utc_end))
        
        departments = cursor.fetchall()
        
        # Add battle rankings and comparisons
        for i, dept in enumerate(departments):
            dept['rank'] = i + 1
            dept['icon'] = {
                'Heat Press': '🔥',
                'Packing': '📦',
                'Picking': '🎯',
                'Labeling': '🏷️'
            }.get(dept['department'], '📋')
            
            if i == 0:
                dept['status'] = 'Leading'
                dept['status_color'] = 'gold'
            elif i == 1:
                dept['status'] = 'Chasing'
                dept['status_color'] = 'silver'
                dept['behind_by'] = float(departments[0]['points'] - dept['points'])
            else:
                dept['status'] = 'Fighting'
                dept['status_color'] = 'bronze'
                dept['behind_by'] = float(departments[0]['points'] - dept['points'])
        
        cursor.close()
        conn.close()
        
        return jsonify(departments)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Recent Activities
@dashboard_bp.route('/activities/recent', methods=['GET'])
@require_api_key
def get_recent_activities():

    """Get recent system activities for the activity feed"""
    limit = request.args.get('limit', 10, type=int)

    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT
            'clock_in' as type,
            CONCAT(e.name, ' clocked in at ', DATE_FORMAT(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'), '%h:%i %p')) as description,
            ct.clock_in as timestamp,
            e.name as employee_name,
            DATE_FORMAT(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago'), '%h:%i %p') as time_str
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE ct.clock_in >= %s AND ct.clock_in < %s

        UNION ALL

        SELECT
            'clock_out' as type,
            CONCAT(e.name, ' clocked out at ', DATE_FORMAT(CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago'), '%h:%i %p')) as description,
            ct.clock_out as timestamp,
            e.name as employee_name,
            DATE_FORMAT(CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago'), '%h:%i %p') as time_str
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE ct.clock_out IS NOT NULL
        AND ct.clock_out >= %s AND ct.clock_out < %s

        ORDER BY timestamp DESC
        LIMIT %s
        """

        cursor.execute(query, (utc_start, utc_end, utc_start, utc_end, limit))
        activities = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify(activities)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Active Alerts
@dashboard_bp.route('/alerts/active', methods=['GET'])
@require_api_key
def get_active_alerts():
    """Get active system alerts"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        alerts = []

        # Check for employees with low productivity
        cursor.execute("""
            SELECT
                e.name,
                ds.points_earned,
                ds.items_processed
            FROM employees e
            JOIN daily_scores ds ON ds.employee_id = e.id
            WHERE ds.score_date = %s
            AND ds.points_earned < 50
            AND ds.points_earned > 0
            ORDER BY ds.points_earned ASC
            LIMIT 3
        """, (ct_date,))
        
        low_performers = cursor.fetchall()
        for emp in low_performers:
            alerts.append({
                'id': len(alerts) + 1,
                'type': 'low_performance',
                'title': 'Performance Alert',
                'message': f"{emp['name']} has only {emp['points_earned']:.1f} points today",
                'severity': 'warning'
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(alerts[:5])
        
    except Exception as e:
        return jsonify([])

# Hourly Analytics
@dashboard_bp.route('/analytics/hourly', methods=['GET'])
@require_api_key
def get_hourly_productivity():
    """Get hourly productivity data for charts"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                HOUR(al.window_start) as hour,
                COUNT(DISTINCT al.employee_id) as active_employees,
                SUM(al.items_count) as items_processed,
                ROUND(SUM(al.items_count * rc.multiplier), 1) as points_earned
            FROM activity_logs al
            JOIN role_configs rc ON rc.id = al.role_id
            WHERE DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = %s
            AND al.source = 'podfactory'
            GROUP BY HOUR(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago'))
            ORDER BY hour
        """, (date,))
        
        hourly_raw = cursor.fetchall()
        
        # Convert to hourly format
        hourly_data = []
        hours = ['6 AM', '7 AM', '8 AM', '9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM', '3 PM', '4 PM', '5 PM']
        
        for i, hour_label in enumerate(hours):
            hour_num = i + 6  # 6 AM = 6, 7 AM = 7, etc.
            data = next((h for h in hourly_raw if h['hour'] == hour_num), None)
            
            if data:
                hourly_data.append({
                    'hour': hour_label,
                    'items_processed': data['items_processed'],
                    'active_employees': data['active_employees'],
                    'points': data['points_earned']
                })
            else:
                hourly_data.append({
                    'hour': hour_label,
                    'items_processed': 0,
                    'active_employees': 0,
                    'points': 0
                })
        
        cursor.close()
        conn.close()
        
        return jsonify(hourly_data)
        
    except Exception as e:
        return jsonify([])

@dashboard_bp.route('/analytics/team-metrics', methods=['GET'])
@dashboard_bp.route('/analytics/team-metrics', methods=['GET'])
@require_api_key
def get_team_metrics():
    """Get overall team metrics"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get metrics with correct calculations
        # Use Central Time consistently for both data and current date comparison
        cursor.execute("""
            SELECT
                -- Count total employees who worked today (clocked in at any point)
                COUNT(DISTINCT ct.employee_id) as total_employees_today,
                -- Count currently clocked in
                COUNT(DISTINCT CASE WHEN ct.clock_out IS NULL THEN ct.employee_id END) as active_employees,
                -- Calculate total hours worked
                COALESCE(ROUND(SUM(GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, UTC_TIMESTAMP())))) / 60.0, 1), 0) as total_hours_worked
            FROM clock_times ct
            WHERE ct.clock_in >= %s AND ct.clock_in < %s
        """, (utc_start, utc_end))

        metrics = cursor.fetchone()

        # Get QC Passed items separately with timezone handling
        cursor.execute("""
            SELECT
                COALESCE(SUM(al.items_count), 0) as items_today
            FROM activity_logs al
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.activity_type = 'QC Passed'
            AND al.source = 'podfactory'
        """, (utc_start, utc_end))

        qc_result = cursor.fetchone()
        metrics['items_today'] = int(qc_result['items_today'] or 0)
        metrics['items_finished'] = metrics['items_today']  # Add this for shop floor

        # Get total points with timezone handling
        cursor.execute("""
            SELECT
                COALESCE(SUM(al.items_count * rc.multiplier), 0) as points_today
            FROM activity_logs al
            JOIN role_configs rc ON rc.id = al.role_id
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.source = 'podfactory'
        """, (utc_start, utc_end))

        points_result = cursor.fetchone()
        metrics['points_today'] = float(points_result['points_today'] or 0)

        # Calculate overall efficiency using role_configs (single source of truth)
        # Formula: Σ(actual_items) / Σ(dept_hours × expected_per_hour) × 100
        # Fixed: Aggregate by employee first to avoid duplicate hours
        cursor.execute("""
            SELECT
                dept_emp.department,
                SUM(dept_emp.emp_items) as dept_items,
                COALESCE(SUM(ct.clock_hours), 0) as dept_hours,
                COUNT(*) as emp_count,
                COUNT(CASE WHEN ct.clock_hours > 0 THEN 1 END) as clocked_emp
            FROM (
                SELECT department, employee_id, SUM(items_count) as emp_items
                FROM activity_logs
                WHERE window_start >= %s AND window_start < %s
                AND source = 'podfactory'
                GROUP BY department, employee_id
            ) dept_emp
            LEFT JOIN (
                SELECT employee_id, SUM(total_minutes) / 60.0 as clock_hours
                FROM clock_times
                WHERE clock_in >= %s AND clock_in < %s
                GROUP BY employee_id
            ) ct ON ct.employee_id = dept_emp.employee_id
            GROUP BY dept_emp.department
        """, (utc_start, utc_end, utc_start, utc_end))
        dept_stats = cursor.fetchall()

        # Get role targets from role_configs
        cursor.execute("SELECT role_name, expected_per_hour FROM role_configs")
        role_targets = {row['role_name']: float(row['expected_per_hour']) for row in cursor.fetchall()}

        # Map department names to role names
        dept_to_role = {
            'Heat Press': 'Heat Pressing',
            'Packing': 'Packing and Shipping',
            'Picking': 'Picker',
            'Labeling': 'Labeler',
            'Film Matching': 'Film Matching'
        }

        total_actual = 0
        total_expected = 0
        for dept in dept_stats:
            dept_name = dept['department']
            role_name = dept_to_role.get(dept_name, dept_name)
            expected_per_hour = role_targets.get(role_name, 60.0)  # Default 60/hr
            dept_hours = float(dept['dept_hours'] or 0)
            dept_items = float(dept['dept_items'] or 0)
            emp_count = int(dept['emp_count'] or 0)
            clocked_emp = int(dept['clocked_emp'] or 0)

            # Estimate hours for unclocked employees
            if clocked_emp > 0 and emp_count > clocked_emp:
                avg_hrs = dept_hours / clocked_emp
                dept_hours += (emp_count - clocked_emp) * avg_hrs

            total_actual += dept_items
            total_expected += dept_hours * expected_per_hour

        overall_efficiency = round((total_actual / total_expected) * 100, 1) if total_expected > 0 else 0
            
        # Get yesterday's data for comparison with timezone handling
        yesterday_ct = ct_date - timedelta(days=1)
        utc_start_yesterday, utc_end_yesterday = tz_helper.ct_date_to_utc_range(yesterday_ct)

        cursor.execute("""
            SELECT COALESCE(SUM(al.items_count), 0) as yesterday_items
            FROM activity_logs al
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.activity_type = 'QC Passed'
            AND al.source = 'podfactory'
        """, (utc_start_yesterday, utc_end_yesterday))

        yesterday = cursor.fetchone()
        yesterday_items = float(yesterday['yesterday_items'] or 0)
        today_items = float(metrics['items_today'] or 0)

        if yesterday_items > 0:
            vs_yesterday = ((today_items - yesterday_items) / yesterday_items) * 100
        else:
            vs_yesterday = 0 if today_items == 0 else 100

        # Get top department for shop floor
        cursor.execute("""
            SELECT
                al.department,
                ROUND(SUM(al.items_count * rc.multiplier), 1) as dept_points
            FROM activity_logs al
            JOIN role_configs rc ON rc.id = al.role_id
            WHERE al.window_start >= %s AND al.window_start < %s
            AND al.source = 'podfactory'
            GROUP BY al.department
            ORDER BY dept_points DESC
            LIMIT 1
        """, (utc_start, utc_end))
        
        top_dept = cursor.fetchone()
        
        result = {
            'active_employees': metrics['active_employees'] or 0,
            'total_employees': metrics['total_employees_today'] or 0,  # Make sure this matches
            'total_employees_today': metrics['total_employees_today'] or 0,
            'items_today': metrics['items_today'] or 0,
            'items_finished': metrics['items_finished'] or 0,  # For shop floor
            'points_today': round(metrics['points_today'] or 0, 1),
            'total_hours_worked': metrics['total_hours_worked'] or 0,
            'overall_efficiency': overall_efficiency,
            'average_items_per_hour': round(metrics['items_today'] / max(metrics['total_hours_worked'], 1), 1),
            'daily_goal': 3000,  # QC passed items target
            'vs_yesterday': round(vs_yesterday, 1),
            'top_department': top_dept['department'] if top_dept else 'None',
            'top_department_points': round(top_dept['dept_points'], 1) if top_dept else 0
        }
        
        cursor.close()
        conn.close()
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        print(f"Error in team metrics: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'active_employees': 0,
            'total_employees': 0,
            'total_employees_today': 0,
            'items_today': 0,
            'items_finished': 0,
            'points_today': 0,
            'total_hours_worked': 0,
            'overall_efficiency': 0,
            'average_items_per_hour': 0,
            'daily_goal': 3000,  # QC passed items target
            'vs_yesterday': 0,
            'top_department': 'None',
            'top_department_points': 0
        })
    
# Employee Stats
@dashboard_bp.route('/employees/<int:employee_id>/stats', methods=['GET'])
@require_api_key
def get_employee_stats(employee_id):
    """Get detailed stats for a specific employee"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                e.id,
                e.name,
                e.current_streak as streak_days,
                COALESCE(ds.items_processed, 0) as items_today,
                COALESCE(ds.points_earned, 0) as points_today,
                CASE
                    WHEN ct.clock_minutes > 0 THEN
                        ROUND(COALESCE(ds.items_processed, 0) / ct.clock_minutes * 60, 1)
                    ELSE 0
                END as items_per_hour
            FROM employees e
            LEFT JOIN daily_scores ds ON ds.employee_id = e.id
                AND ds.score_date = %s
            LEFT JOIN (
                SELECT employee_id,
                       MIN(clock_in) as clock_in,
                       MAX(clock_out) as clock_out,
                       GREATEST(0, TIMESTAMPDIFF(MINUTE, MIN(clock_in), COALESCE(MAX(clock_out), UTC_TIMESTAMP()))) as clock_minutes
                FROM clock_times
                WHERE clock_in >= %s AND clock_in < %s
                GROUP BY employee_id
            ) ct ON ct.employee_id = e.id
            WHERE e.id = %s
        """, (ct_date, utc_start, utc_end, employee_id))

        employee = cursor.fetchone()

        if not employee:
            return jsonify({'error': 'Employee not found'}), 404

        # Get rank
        cursor.execute("""
            SELECT COUNT(*) + 1 as rank
            FROM daily_scores
            WHERE score_date = %s
            AND points_earned > (
                SELECT points_earned
                FROM daily_scores
                WHERE employee_id = %s
                AND score_date = %s
            )
        """, (ct_date, employee_id, ct_date))
        
        rank_data = cursor.fetchone()
        
        stats = {
            'id': employee['id'],
            'name': employee['name'],
            'streak_days': employee['streak_days'] or 0,
            'items_today': employee['items_today'],
            'points_today': round(employee['points_today'], 1),
            'items_per_hour': round(employee['items_per_hour'], 1),
            'rank': rank_data['rank'] if rank_data else 999
        }
        
        cursor.close()
        conn.close()
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# # Employees List
# @dashboard_bp.route('/employees', methods=['GET'])
# @require_api_key
# def get_employees():
#     """Get all active employees"""
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)
        
#         cursor.execute("""
#             SELECT 
#                 e.id,
#                 e.name,
#                 e.name as full_name
#             FROM employees e
#             WHERE e.is_active = 1
#             ORDER BY e.name
#         """)
        
#         employees = cursor.fetchall()
        
#         cursor.close()
#         conn.close()
        
#         return jsonify(employees)
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# Single Employee
@dashboard_bp.route('/employees/<int:employee_id>', methods=['GET'])
@require_api_key
def get_employee(employee_id):
    """Get specific employee details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                e.id,
                e.name,
                e.name as full_name,
                e.current_streak
            FROM employees e
            WHERE e.id = %s
        """, (employee_id,))
        
        employee = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if employee:
            name_parts = employee['name'].split(' ', 1)
            employee['first_name'] = name_parts[0]
            employee['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
            return jsonify(employee)
        else:
            return jsonify({'error': 'Employee not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Employee Activities
@dashboard_bp.route('/activities', methods=['GET'])
@require_api_key
def get_employee_activities():
    """Get activities for employee portal"""
    employee_id = request.args.get('employee_id', type=int)
    limit = request.args.get('limit', 10, type=int)

    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if employee_id:
            cursor.execute("""
                SELECT
                    al.activity_type as type,
                    CONCAT(al.items_count, ' items - ', al.activity_type) as description,
                    al.window_start as timestamp
                FROM activity_logs al
                WHERE al.employee_id = %s
                AND al.window_start >= %s AND al.window_start < %s
                ORDER BY al.window_start DESC
                LIMIT %s
            """, (employee_id, utc_start, utc_end, limit))
            
            activities = cursor.fetchall()
        else:
            activities = []
        
        cursor.close()
        conn.close()
        
        return jsonify(activities)
        
    except Exception as e:
        return jsonify([])

# Record Activity from PodFactory
@dashboard_bp.route('/activities/activity', methods=['POST'])
@require_api_key
def record_activity():
    """Record activity from PodFactory with duplicate checking"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['employee_id', 'quantity']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Extract metadata
        metadata = data.get('metadata', {})
        podfactory_id = str(metadata.get('podfactory_id', ''))
        user_role = metadata.get('user_role', '')
        action = metadata.get('action', 'item_scan')
        
        # Get role_id from user_role
        role_id = metadata.get('role_id') or ACTION_TO_ROLE_ID.get(action, 3)
        
        # Check if this PodFactory activity already exists
        if podfactory_id:
            cursor.execute("""
                SELECT id FROM activity_logs 
                WHERE reference_id = %s AND source = 'podfactory'
                LIMIT 1
            """, (podfactory_id,))
            
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({
                    'success': True,
                    'message': 'Activity already processed',
                    'status': 'duplicate'
                }), 200
        
        # Get timestamp
        timestamp = data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Generate unique report_id
        report_id = f"PF_{podfactory_id or datetime.now().strftime('%Y%m%d%H%M%S%f')}_{data['employee_id']}"
        
        # Calculate window times
        window_start = timestamp

        # Always calculate duration_minutes
        window_end_str = data.get('window_end')
        if window_end_str:
            # Use the actual window_end from PodFactory
            window_end = datetime.fromisoformat(window_end_str.replace('Z', '+00:00'))
            # Calculate duration from actual window times
            duration_minutes = int((window_end - window_start).total_seconds() / 60)
        else:
            # Fallback to duration from metadata or default
            duration_minutes = metadata.get('duration_minutes', 10)
            window_end = window_start + timedelta(minutes=duration_minutes)
        
        # Get department from action
        department = ACTION_TO_DEPARTMENT_MAP.get(action, data.get('department', 'Unknown'))
        # ADD THIS SECTION - Convert to naive UTC datetime for MySQL
        if window_start and window_start.tzinfo:
        # If timezone-aware, convert to UTC and remove timezone info
            window_start = window_start.astimezone(pytz.UTC).replace(tzinfo=None)
            
        if window_end and window_end.tzinfo:
        # If timezone-aware, convert to UTC and remove timezone info
            window_end = window_end.astimezone(pytz.UTC).replace(tzinfo=None)
        # Insert activity
        cursor.execute("""
            INSERT INTO activity_logs 
            (report_id, employee_id, activity_type, scan_type, role_id, 
             items_count, window_start, window_end, department, 
             source, reference_id, duration_minutes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            report_id,
            data['employee_id'],
            action,
            data.get('scan_type', 'item_scan'),
            role_id,
            data['quantity'],
            window_start,
            window_end,
            department,
            metadata.get('source', 'podfactory'),
            podfactory_id,
            duration_minutes
        ))
        
        activity_id = cursor.lastrowid
        
        # Calculate points using role multiplier
        cursor.execute("""
            SELECT multiplier FROM role_configs WHERE id = %s
        """, (role_id,))
        
        multiplier_row = cursor.fetchone()
        multiplier = float(multiplier_row[0]) if multiplier_row else 1.0
        points = data['quantity'] * multiplier
        
        # Update daily scores
        score_date = window_start.date()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'activity_id': activity_id,
            'points_earned': round(points, 2),
            'message': f'Activity recorded: {data["quantity"]} items = {points:.1f} points',
            'status': 'created'
        }), 200
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error recording activity: {error_msg}")
        print(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

@dashboard_bp.route('/activities/bulk', methods=['POST'])
@require_api_key
def record_activities_bulk():
    """Record multiple activities from PodFactory in bulk"""
    try:
        activities = request.get_json()
        
        if not isinstance(activities, list):
            return jsonify({'error': 'Expected a list of activities'}), 400
        
        if not activities:
            return jsonify({'success': True, 'message': 'No activities to process'}), 200
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Track results
        created_count = 0
        duplicate_count = 0
        error_count = 0
        total_points = 0
        
        # Collect all podfactory IDs to check for duplicates
        podfactory_ids = []
        for activity in activities:
            metadata = activity.get('metadata', {})
            pf_id = str(metadata.get('podfactory_id', ''))
            if pf_id:
                podfactory_ids.append(pf_id)
        
        # Check existing activities in one query
        existing_ids = set()
        if podfactory_ids:
            placeholders = ','.join(['%s'] * len(podfactory_ids))
            cursor.execute(f"""
                SELECT reference_id 
                FROM activity_logs 
                WHERE reference_id IN ({placeholders}) 
                AND source = 'podfactory'
            """, podfactory_ids)
            existing_ids = {row[0] for row in cursor.fetchall()}
        
        # Prepare batch inserts
        activity_values = []
        score_updates = {}  # employee_id -> (date, items, points)
        
        for activity in activities:
            try:
                # Validate required fields
                if 'employee_id' not in activity or 'quantity' not in activity:
                    error_count += 1
                    continue
                
                # Extract metadata
                metadata = activity.get('metadata', {})
                podfactory_id = str(metadata.get('podfactory_id', ''))
                
                # Skip if duplicate
                if podfactory_id and podfactory_id in existing_ids:
                    duplicate_count += 1
                    continue
                
                # Get data
                user_role = metadata.get('user_role', '')
                action = metadata.get('action', 'item_scan')
                role_id = metadata.get('role_id') or ACTION_TO_ROLE_ID.get(action, 3)
                
                # Get timestamp
                timestamp = activity.get('timestamp', datetime.now())
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                # Generate unique report_id
                report_id = f"PF_{podfactory_id or datetime.now().strftime('%Y%m%d%H%M%S%f')}_{activity['employee_id']}"
                
                # Calculate window times
                window_start = timestamp
                duration_minutes = metadata.get('duration_minutes', 10)
                window_end = window_start + timedelta(minutes=duration_minutes)
                # ADD THIS - Convert to naive UTC datetime for MySQL
                if window_start and window_start.tzinfo:
                    window_start = window_start.astimezone(pytz.UTC).replace(tzinfo=None)
                    
                if window_end and window_end.tzinfo:
                    window_end = window_end.astimezone(pytz.UTC).replace(tzinfo=None)
                
                # Get department
                department = ACTION_TO_DEPARTMENT_MAP.get(action, activity.get('department', 'Unknown'))
                
                # Add to batch
                activity_values.append((
                    report_id,
                    activity['employee_id'],
                    action,
                    activity.get('scan_type', 'item_scan'),
                    role_id,
                    activity['quantity'],
                    window_start,
                    window_end,
                    department,
                    metadata.get('source', 'podfactory'),
                    podfactory_id,
                    duration_minutes
                ))
                
                # Calculate points
                cursor.execute("SELECT multiplier FROM role_configs WHERE id = %s", (role_id,))
                multiplier_row = cursor.fetchone()
                multiplier = float(multiplier_row[0]) if multiplier_row else 1.0
                points = activity['quantity'] * multiplier
                
                # Track for daily scores update
                score_date = window_start.date()
                emp_id = activity['employee_id']
                
                if emp_id not in score_updates:
                    score_updates[emp_id] = {}
                if score_date not in score_updates[emp_id]:
                    score_updates[emp_id][score_date] = {'items': 0, 'points': 0}
                
                score_updates[emp_id][score_date]['items'] += activity['quantity']
                score_updates[emp_id][score_date]['points'] += points
                
                created_count += 1
                total_points += points
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing activity: {str(e)}")
                continue
        
        # Bulk insert activities
        if activity_values:
            cursor.executemany("""
                INSERT INTO activity_logs 
                (report_id, employee_id, activity_type, scan_type, role_id, 
                 items_count, window_start, window_end, department, 
                 source, reference_id, duration_minutes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, activity_values)
              
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'created': created_count,
            'duplicates': duplicate_count,
            'errors': error_count,
            'total_points': round(total_points, 2),
            'message': f'Processed {len(activities)} activities: {created_count} created, {duplicate_count} duplicates, {error_count} errors'
        }), 200
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        logger.error(f"Error in bulk activity recording: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({'error': error_msg}), 500

# Add these endpoints to your dashboard.py file after the existing endpoints

# Bottleneck Detection System
@dashboard_bp.route('/bottleneck/current', methods=['GET'])
@require_api_key
def get_current_bottleneck():
    """Get real-time bottleneck detection data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get current date/time in Central
        central_now = get_central_datetime()
        current_date = central_now.date()
        
        # Define the workflow sequence
        workflow_sequence = [
            ('Picking', 'Labeling'),
            ('Labeling', 'Film Matching'),
            ('Film Matching', 'In Production'),  # In Production = Heat Press
            ('In Production', 'QC Passed')  # QC Passed = Shipping
        ]
        
        # Get flow rates for last 30 minutes - FIXED to use UTC
        flow_query = """
        SELECT 
            al.activity_type,
            COUNT(DISTINCT al.employee_id) as workers,
            COALESCE(SUM(al.items_count), 0) as items_last_30min,
            COUNT(*) as activity_count,
            MIN(al.window_start) as earliest_activity,
            MAX(al.window_end) as last_activity,
            TIMESTAMPDIFF(MINUTE, MAX(al.window_end), UTC_TIMESTAMP()) as minutes_since_last
        FROM activity_logs al
        WHERE al.window_start >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 30 MINUTE)
            AND al.source = 'podfactory'
        GROUP BY al.activity_type
        """

        # Execute without date parameter
        cursor.execute(flow_query)
        flow_data = cursor.fetchall()

        # Add debug logging
        print(f"\nBottleneck Detection Debug at {datetime.now()}:")
        print(f"Found {len(flow_data)} active stations in last 30 minutes")
        
        # Define display names mapping EARLY (before any usage)
        display_names = {
            'Picking': 'Picking',
            'Labeling': 'Labeling', 
            'Film Matching': 'Film Matching',
            'In Production': 'Heat Press',
            'QC Passed': 'Shipping'
        }

        # Define station names order
        station_names = ['Picking', 'Labeling', 'Film Matching', 'In Production', 'QC Passed']
        
        for row in flow_data:
            print(f"  {row['activity_type']}: {row['items_last_30min']} items, last activity {row['minutes_since_last']} mins ago")
        if not flow_data:
            print("WARNING: No activity data found for bottleneck analysis")
        
        # Create a dict for easy lookup and calculate hourly rates
        flow_dict = {}
        for row in flow_data:
            # Calculate items per hour (double the 30-minute count)
            items_per_hour = int(row.get('items_last_30min', 0) * 2)
            
            flow_dict[row['activity_type']] = {
                'activity_type': row['activity_type'],
                'workers': row['workers'],
                'items_last_30min': row['items_last_30min'],
                'items_per_hour': items_per_hour,
                'last_activity': row['last_activity'],
                'minutes_since_last': row.get('minutes_since_last')
            }

        
        # Calculate queue buildup and bottlenecks
        stations = []
        bottlenecks = []
        
        for i, activity in enumerate(station_names):
            # Get the actual data
            station_data = flow_dict.get(activity, {
                'activity_type': activity,
                'workers': 0,
                'items_last_30min': 0,
                'items_per_hour': 0,
                'last_activity': None,
                'minutes_since_last': None
            })
            
            # Get today's total for this station (for context)
            cursor.execute("""
                SELECT COALESCE(SUM(items_count), 0) as total_today
                FROM activity_logs
                WHERE activity_type = %s
                AND DATE(window_start) = %s
                AND source = 'podfactory'
            """, (activity, current_date))
            today_total = cursor.fetchone()['total_today']
            
            # Calculate input rate (from previous station)
            if i > 0:
                prev_station = station_names[i-1]
                prev_data = flow_dict.get(prev_station, {})
                input_rate = int(prev_data.get('items_per_hour', 0))
            else:
                input_rate = 0
            
            # Output rate is this station's rate
            output_rate = int(station_data.get('items_per_hour', 0))
            workers = int(station_data.get('workers', 0))
            minutes_since_last = station_data.get('minutes_since_last')
            
            # Queue growth rate
            queue_growth = input_rate - output_rate if i > 0 else 0
            
            # Estimate queue size
            estimated_queue = max(0, queue_growth * 0.5)  # Half hour of growth
            
            # SMART STATUS DETERMINATION
            # Check current hour (for time-based context)
            current_hour = central_now.hour
            
            # Determine status based on multiple factors
            if workers == 0:  # No workers at station
                if minutes_since_last is None:
                    # Never had activity today
                    if current_hour < 10:
                        status = 'not_started'
                        status_level = 'idle'
                    else:
                        status = 'idle'
                        status_level = 'idle'
                elif minutes_since_last > 60:
                    # No activity for over an hour
                    if today_total > 100:  # Had significant activity earlier
                        # Check if downstream stations are still active
                        downstream_active = False
                        if i < len(station_names) - 1:
                            for j in range(i + 1, len(station_names)):
                                downstream_data = flow_dict.get(station_names[j], {})
                                if downstream_data.get('workers', 0) > 0:
                                    downstream_active = True
                                    break
                        
                        if downstream_active:
                            status = 'complete'
                            status_level = 'complete'
                        else:
                            status = 'idle'
                            status_level = 'idle'
                    else:
                        status = 'idle'
                        status_level = 'idle'
                elif minutes_since_last <= 30:
                    # Recent activity but no workers now
                    status = 'recently_stopped'
                    status_level = 'warning'
                else:
                    status = 'idle'
                    status_level = 'idle'
            
            elif workers > 0:  # Workers present at station
                if output_rate == 0:
                    # Workers present but no production
                    if minutes_since_last and minutes_since_last < 10:
                        # Just started, give them time
                        status = 'warming_up'
                        status_level = 'normal'
                    else:
                        # This is a real problem - workers but no output
                        status = 'critical'
                        status_level = 'critical'
                elif queue_growth > 50:
                    # Major bottleneck
                    status = 'bottleneck'
                    status_level = 'critical'
                elif queue_growth > 20:
                    # Minor bottleneck
                    status = 'slow'
                    status_level = 'warning'
                elif output_rate < 10 and workers >= 3:
                    # Too many workers for low output
                    status = 'inefficient'
                    status_level = 'warning'
                else:
                    # Everything flowing well
                    status = 'flowing'
                    status_level = 'good'
            
            # Special case for first station (Picking)
            if activity == 'Picking' and status == 'idle' and today_total > 500:
                status = 'complete'
                status_level = 'complete'
            
            # Build station info
            station_info = {
                'name': display_names.get(activity, activity),
                'activity_type': activity,
                'workers': workers,
                'input_rate': input_rate,
                'output_rate': output_rate,
                'items_per_hour': output_rate,
                'queue_growth': queue_growth,
                'estimated_queue': int(estimated_queue),
                'status': status,
                'status_level': status_level,
                'last_activity': station_data.get('last_activity'),
                'minutes_since_last': minutes_since_last,
                'today_total': today_total  # Add this for frontend display
            }
            
            stations.append(station_info)
            
            # Only track bottlenecks for actual problems (not idle/complete stations)
            if status_level in ['critical', 'warning'] and workers > 0 and status != 'warming_up':
                bottlenecks.append({
                    'station': display_names.get(activity, activity),
                    'severity': status_level,
                    'queue_growth': queue_growth,
                    'workers': workers,
                    'status': status
                })
        
        # Find the PRIMARY bottleneck (worst queue growth)
        primary_bottleneck = None
        if bottlenecks:
            primary_bottleneck = max(bottlenecks, key=lambda x: x['queue_growth'])
        
        # FIXED: Get available workers who can help - using separate queries to avoid GROUP BY issues
        # First get all clocked-in employees
        clocked_in_query = """
        SELECT DISTINCT e.id, e.name
        FROM employees e
        INNER JOIN clock_times ct ON ct.employee_id = e.id
        WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
            AND ct.clock_out IS NULL
            AND e.is_active = 1
        """
        
        cursor.execute(clocked_in_query, (current_date,))
        clocked_in_workers = cursor.fetchall()
        
        available_workers = []
        
        # For each worker, get their current activity and skills
        for worker in clocked_in_workers:
            # Get current activity (last 30 min)
            current_activity_query = """
            SELECT al.activity_type 
            FROM activity_logs al
            WHERE al.employee_id = %s 
                AND al.window_start >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
                AND DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = %s
            ORDER BY al.window_start DESC
            LIMIT 1
            """
            cursor.execute(current_activity_query, (worker['id'], current_date))
            current_result = cursor.fetchone()
            current_activity = current_result['activity_type'] if current_result else None
            
            # Get skills (activities done in past 7 days)
            skills_query = """
            SELECT DISTINCT al.activity_type
            FROM activity_logs al
            WHERE al.employee_id = %s
                AND al.window_start >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                AND al.source = 'podfactory'
            """
            cursor.execute(skills_query, (worker['id'],))
            skills = [row['activity_type'] for row in cursor.fetchall()]
            
            # Get performance scores for each skill
            skill_performance = {}
            if skills:
                performance_query = """
                SELECT 
                    al.activity_type,
                    ROUND(AVG(al.items_count), 0) as avg_items
                FROM activity_logs al
                WHERE al.employee_id = %s
                    AND al.window_start >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    AND al.source = 'podfactory'
                    AND al.activity_type IN (%s)
                GROUP BY al.activity_type
                """ % (
                    '%s',
                    ','.join(['%s'] * len(skills))
                )
                
                cursor.execute(performance_query, (worker['id'], *skills))
                for row in cursor.fetchall():
                    skill_performance[row['activity_type']] = int(row['avg_items'])
            
            # Check if worker can help with bottleneck
            can_help = False
            if primary_bottleneck:
                # Find the activity type that corresponds to the bottleneck station
                bottleneck_activity = None
                for activity, display in display_names.items():
                    if display == primary_bottleneck['station']:
                        bottleneck_activity = activity
                        break
                
                can_help = bottleneck_activity in skills if bottleneck_activity else False
            
            available_workers.append({
                'id': worker['id'],
                'name': worker['name'],
                'current_station': display_names.get(current_activity, current_activity or 'Unknown'),
                'current_activity': current_activity,
                'skills': skills,
                'skill_performance': skill_performance,
                'can_help_bottleneck': can_help
            })
        
        # Generate recommendations
        recommendations = []
        if primary_bottleneck:
            # Find workers who can help
            helpers = [w for w in available_workers if w['can_help_bottleneck']]
            
            if helpers:
                # Sort by performance in the bottleneck activity
                activity_key = None
                for k, v in display_names.items():
                    if v == primary_bottleneck['station']:
                        activity_key = k
                        break

                if activity_key:
                    helpers.sort(key=lambda x: x['skill_performance'].get(activity_key, 0), reverse=True)
                
                # Recommend top 2-3 workers
                for helper in helpers[:3]:
                    if helper['current_station'] != primary_bottleneck['station']:
                        recommendations.append({
                            'action': 'reassign',
                            'worker': helper['name'],
                            'from': helper['current_station'],
                            'to': primary_bottleneck['station'],
                            'impact': 'high',
                            'reason': f"Can help clear {primary_bottleneck['station']} bottleneck"
                        })
        
        # Calculate predictions
        predictions = []
        for station in stations:
            if station['queue_growth'] > 0:
                # Time to critical (queue > 300 items)
                if station['estimated_queue'] < 300:
                    hours_to_critical = (300 - station['estimated_queue']) / station['queue_growth'] if station['queue_growth'] > 0 else 999
                    if hours_to_critical < 2:
                        predictions.append({
                            'station': station['name'],
                            'warning': f"Queue will exceed 300 items in {hours_to_critical:.1f} hours",
                            'severity': 'high' if hours_to_critical < 0.5 else 'medium'
                        })
            elif station['queue_growth'] < -10 and station['name'] != 'Picking':
                # Station clearing too fast - might starve
                hours_to_empty = station['estimated_queue'] / abs(station['queue_growth']) if station['queue_growth'] < 0 else 999
                if hours_to_empty < 1:
                    predictions.append({
                        'station': station['name'],
                        'warning': f"Will run out of work in {hours_to_empty:.1f} hours",
                        'severity': 'medium'
                    })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'timestamp': central_now.isoformat(),
            'stations': stations,
            'primary_bottleneck': primary_bottleneck,
            'available_workers': available_workers,
            'recommendations': recommendations,
            'predictions': predictions,
            'summary': {
                'total_workers_active': len(available_workers),
                'total_items_flowing': sum(s['output_rate'] for s in stations),
                'bottleneck_count': len(bottlenecks)
            }
        })
        
    except Exception as e:
        import traceback
        logger.error(f"Error in bottleneck detection: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
    
@dashboard_bp.route('/bottleneck/history', methods=['GET'])
@require_api_key
def get_bottleneck_history():
    """Get historical bottleneck patterns"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get hourly bottleneck data
        query = """
        SELECT 
            DATE_FORMAT(al.window_start, '%Y-%m-%d %H:00') as hour,
            al.activity_type,
            COUNT(DISTINCT al.employee_id) as workers,
            SUM(al.items_count) as items_processed,
            ROUND(AVG(al.items_count / TIMESTAMPDIFF(MINUTE, al.window_start, al.window_end) * 60), 1) as avg_rate
        FROM activity_logs al
        WHERE al.window_start >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            AND al.source = 'podfactory'
        GROUP BY hour, al.activity_type
        ORDER BY hour DESC, al.activity_type
        """
        
        cursor.execute(query, (hours,))
        history = cursor.fetchall()
        
        # Process into hourly summaries
        hourly_data = {}
        for row in history:
            hour = row['hour']
            if hour not in hourly_data:
                hourly_data[hour] = {
                    'hour': hour,
                    'stations': {},
                    'bottlenecks': []
                }
            
            hourly_data[hour]['stations'][row['activity_type']] = {
                'workers': row['workers'],
                'items': row['items_processed'],
                'rate': float(row['avg_rate'])
            }
        
        # Identify historical bottlenecks
        workflow = ['Picking', 'Labeling', 'Film Matching', 'In Production', 'QC Passed']
        
        for hour_key, data in hourly_data.items():
            for i in range(1, len(workflow)):
                prev_station = workflow[i-1]
                curr_station = workflow[i]
                
                if prev_station in data['stations'] and curr_station in data['stations']:
                    prev_rate = data['stations'][prev_station]['rate']
                    curr_rate = data['stations'][curr_station]['rate']
                    
                    if prev_rate > curr_rate * 1.2:  # 20% slower = bottleneck
                        data['bottlenecks'].append({
                            'station': curr_station,
                            'backup_rate': prev_rate - curr_rate
                        })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'hours_analyzed': hours,
            'hourly_data': list(hourly_data.values())
        })
        
    except Exception as e:
        logger.error(f"Error getting bottleneck history: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/employees', methods=['GET'])
@require_api_key
def get_employees():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get all employees with their mapping info and PIN status
        query = """
            SELECT
                e.id,
                e.name,
                e.email,
                e.connecteam_user_id,
                e.is_active,
                GROUP_CONCAT(DISTINCT m.podfactory_email) as podfactory_emails,
                CASE WHEN ea.pin IS NOT NULL THEN 1 ELSE 0 END as has_pin
            FROM employees e
            LEFT JOIN employee_podfactory_mapping_v2 m ON e.id = m.employee_id
            LEFT JOIN employee_auth ea ON e.id = ea.employee_id
            GROUP BY e.id
            ORDER BY e.name
        """
        cursor.execute(query)
        employees = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'employees': employees
        })
        
    except Exception as e:
        print(f"Error fetching employees: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/employees/<int:employee_id>/mapping', methods=['POST'])
@require_api_key
def update_employee_mapping(employee_id):
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update Connecteam ID
        if 'connecteam_user_id' in data:
            cursor.execute("""
                UPDATE employees 
                SET connecteam_user_id = %s 
                WHERE id = %s
            """, (data['connecteam_user_id'], employee_id))
        
        # Update PodFactory emails
        if 'podfactory_emails' in data:
            # First, delete existing mappings
            cursor.execute("""
                DELETE FROM employee_podfactory_mapping_v2 
                WHERE employee_id = %s
            """, (employee_id,))
            
            # Add new mappings
            emails = [email.strip() for email in data['podfactory_emails'].split(',') if email.strip()]
            for email in emails:
                cursor.execute("""
                    INSERT INTO employee_podfactory_mapping_v2 
                    (employee_id, podfactory_email, similarity_score, confidence_level, is_verified)
                    VALUES (%s, %s, %s, %s, %s)
                """, (employee_id, email, 1.00, 'manual', 1))  # Changed to 1.00
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error updating mapping: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@dashboard_bp.route('/unmapped-users', methods=['GET'])
@require_api_key
def get_unmapped_users():
    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Get fresh user data from Connecteam API
        connecteam_headers = {
            'X-API-Key': os.getenv('CONNECTEAM_API_KEY'),
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://api.connecteam.com/users/v1/users',
            headers=connecteam_headers,
            params={'limit': 100},
            verify=False  # Note: In production, handle SSL properly
        )
        
        connecteam_users = []
        if response.status_code == 200:
            data = response.json()
            users = data.get('data', {}).get('users', [])
            
            for user in users:
                if not user.get('isArchived', False):  # Only active users
                    connecteam_users.append({
                        'connecteam_id': str(user.get('userId')),
                        'name': f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
                    })
        
        # Get PodFactory emails from mapping table
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT DISTINCT podfactory_email as email
            FROM employee_podfactory_mapping_v2
            ORDER BY podfactory_email
        """)
        podfactory_emails = [row['email'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'connecteam_users': connecteam_users,
            'podfactory_emails': podfactory_emails
        })
        
    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify({'connecteam_users': [], 'podfactory_emails': []})

@dashboard_bp.route('/debug-mapping', methods=['GET'])
@require_api_key
def debug_mapping():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Count total Connecteam users in clock_times
        cursor.execute("SELECT COUNT(DISTINCT connecteam_user_id) as total FROM clock_times WHERE connecteam_user_id IS NOT NULL")
        result = cursor.fetchone()
        total_ct = result['total'] if result else 0
        
        # Count mapped Connecteam IDs in employees
        cursor.execute("SELECT COUNT(*) as mapped FROM employees WHERE connecteam_user_id IS NOT NULL AND connecteam_user_id != ''")
        result = cursor.fetchone()
        mapped = result['mapped'] if result else 0
        
        # Get sample of Connecteam users from clock_times
        cursor.execute("SELECT DISTINCT connecteam_user_id, name FROM clock_times WHERE connecteam_user_id IS NOT NULL LIMIT 5")
        sample_ct = cursor.fetchall()
        
        # Get sample of unmapped employees
        cursor.execute("SELECT id, name, connecteam_user_id FROM employees WHERE connecteam_user_id IS NULL OR connecteam_user_id = '' LIMIT 5")
        unmapped_emp = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_connecteam_users': total_ct,
            'mapped_employees': mapped,
            'sample_connecteam': sample_ct,
            'unmapped_employees': unmapped_emp
        })
    except Exception as e:
        print(f"Debug error: {e}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/bottleneck/reassign', methods=['POST'])
@require_api_key
def reassign_worker():
    """Record a worker reassignment (for tracking purposes)"""
    try:
        data = request.get_json()
        
        # In a real system, this would:
        # 1. Send notification to worker
        # 2. Update station assignments
        # 3. Log the reassignment
        
        # For now, just return success
        return jsonify({
            'success': True,
            'message': f"Reassignment recorded: {data['worker_name']} to {data['to_station']}",
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@dashboard_bp.route('/employees/payrates', methods=['GET'])
@require_api_key
def get_all_payrates():
    """Get all employee payrates"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                e.id,
                e.name,
                COALESCE(ep.pay_rate, 13.00) as pay_rate,
                COALESCE(ep.pay_type, 'hourly') as pay_type,
                ep.effective_date,
                ep.notes,
                CASE 
                    WHEN ep.pay_type = 'salary' THEN ROUND(ep.pay_rate / 26 / 8, 2)
                    ELSE ep.pay_rate
                END as hourly_equivalent
            FROM employees e
            LEFT JOIN employee_payrates ep ON e.id = ep.employee_id
            WHERE e.is_active = 1
            ORDER BY e.name
        """)
        
        payrates = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'payrates': payrates})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/employees/<int:employee_id>/payrate', methods=['POST'])
@require_api_key
def update_employee_payrate(employee_id):
    """Update payrate for specific employee"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        data = request.json
        pay_rate = data.get('pay_rate')
        pay_type = data.get('pay_type', 'hourly')
        notes = data.get('notes', '')

        if pay_rate is None:
            return jsonify({'success': False, 'error': 'pay_rate is required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if payrate record exists
        cursor.execute("SELECT id FROM employee_payrates WHERE employee_id = %s", (employee_id,))
        exists = cursor.fetchone()

        if exists:
            # Update existing
            cursor.execute("""
                UPDATE employee_payrates
                SET pay_rate = %s,
                    pay_type = %s,
                    notes = %s
                WHERE employee_id = %s
            """, (pay_rate, pay_type, notes, employee_id))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO employee_payrates (employee_id, pay_rate, pay_type, effective_date, notes)
                VALUES (%s, %s, %s, %s, %s)
            """, (employee_id, pay_rate, pay_type, ct_date, notes))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Payrate updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/employees/<int:employee_id>/archive', methods=['POST'])
@require_api_key
def archive_employee(employee_id):
    """Archive an employee (soft delete)"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if employee is currently clocked in
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM time_tracking
            WHERE employee_id = %s
            AND clock_out_time IS NULL
            AND clock_in_time >= %s AND clock_in_time < %s
        """, (employee_id, utc_start, utc_end))
        
        result = cursor.fetchone()
        if result['count'] > 0:
            return jsonify({'success': False, 'error': 'Cannot archive employee who is currently clocked in'}), 400
        
        # Archive the employee
        cursor.execute("""
            UPDATE employees 
            SET is_active = 0, 
                archived_at = NOW() 
            WHERE id = %s
        """, (employee_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Employee archived successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/employees/archived', methods=['GET'])
@require_api_key
def get_archived_employees():
    """Get list of archived employees"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, name, email, archived_at 
            FROM employees 
            WHERE archived_at IS NOT NULL 
            ORDER BY archived_at DESC
        """)
        
        archived = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'archived': archived})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/employees/<int:employee_id>/restore', methods=['POST'])
@require_api_key
def restore_employee(employee_id):
    """Restore an archived employee"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE employees 
            SET is_active = 1, 
                archived_at = NULL 
            WHERE id = %s
        """, (employee_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Employee restored successfully'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============= PENDING VERIFICATION ENDPOINTS =============

@dashboard_bp.route('/employees/pending-verification', methods=['GET'])
@require_api_key
def get_pending_verifications():
    """Get all unverified PodFactory email mappings for manager review"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get unverified mappings with employee info and recent activity count
        cursor.execute("""
            SELECT
                m.id as mapping_id,
                m.employee_id,
                e.name as employee_name,
                e.connecteam_user_id,
                m.podfactory_email,
                m.podfactory_name,
                m.similarity_score,
                m.confidence_level,
                m.created_at,
                (SELECT COUNT(*) FROM activity_logs al
                 WHERE al.employee_id = m.employee_id
                 AND al.window_end > DATE_SUB(NOW(), INTERVAL 7 DAY)) as recent_activity_count
            FROM employee_podfactory_mapping_v2 m
            JOIN employees e ON m.employee_id = e.id
            WHERE m.is_verified = 0
            AND e.is_active = 1
            ORDER BY m.created_at DESC
        """)
        pending = cursor.fetchall()

        # Convert datetime objects to strings for JSON
        for item in pending:
            if item.get('created_at'):
                item['created_at'] = item['created_at'].isoformat()
            if item.get('similarity_score'):
                item['similarity_score'] = float(item['similarity_score'])

        # Get count of unmapped Connecteam employees (no podfactory emails at all)
        cursor.execute("""
            SELECT COUNT(*) as unmapped_count
            FROM employees e
            LEFT JOIN employee_podfactory_mapping_v2 m ON e.id = m.employee_id
            WHERE e.is_active = 1
            AND e.connecteam_user_id IS NOT NULL
            AND m.id IS NULL
        """)
        unmapped = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'pending': pending,
            'pending_count': len(pending),
            'unmapped_connecteam_count': unmapped['unmapped_count'] if unmapped else 0
        })

    except Exception as e:
        logger.error(f"Error getting pending verifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/employees/mapping/<int:mapping_id>/verify', methods=['POST'])
@require_api_key
def verify_mapping(mapping_id):
    """Approve or reject a pending mapping"""
    try:
        data = request.json
        action = data.get('action')  # 'approve' or 'reject'
        verified_by = data.get('verified_by', 'manager')

        if action not in ['approve', 'reject']:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        if action == 'approve':
            # Mark as verified
            cursor.execute("""
                UPDATE employee_podfactory_mapping_v2
                SET is_verified = 1,
                    verified_by = %s,
                    verified_at = NOW(),
                    confidence_level = 'MANUAL'
                WHERE id = %s
            """, (verified_by, mapping_id))
        else:
            # Reject - delete the mapping
            cursor.execute("""
                DELETE FROM employee_podfactory_mapping_v2
                WHERE id = %s
            """, (mapping_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Mapping {action}d successfully'
        })

    except Exception as e:
        logger.error(f"Error verifying mapping: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/employees/mapping/<int:mapping_id>/reassign', methods=['POST'])
@require_api_key
def reassign_mapping(mapping_id):
    """Reassign a PodFactory email to a different employee"""
    try:
        data = request.json
        new_employee_id = data.get('employee_id')
        verified_by = data.get('verified_by', 'manager')

        if not new_employee_id:
            return jsonify({'success': False, 'error': 'Employee ID required'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update the mapping to new employee and mark verified
        cursor.execute("""
            UPDATE employee_podfactory_mapping_v2
            SET employee_id = %s,
                is_verified = 1,
                verified_by = %s,
                verified_at = NOW(),
                confidence_level = 'MANUAL',
                notes = CONCAT(IFNULL(notes, ''), ' Reassigned from original auto-mapping')
            WHERE id = %s
        """, (new_employee_id, verified_by, mapping_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Mapping reassigned successfully'
        })

    except Exception as e:
        logger.error(f"Error reassigning mapping: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/employees/bulk-verify', methods=['POST'])
@require_api_key
def bulk_verify_mappings():
    """Bulk approve all mappings where names match exactly"""
    try:
        data = request.json
        verified_by = data.get('verified_by', 'manager')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Approve all where employee name matches podfactory name (case insensitive)
        # Using COLLATE to handle different table collations
        cursor.execute("""
            UPDATE employee_podfactory_mapping_v2 m
            JOIN employees e ON m.employee_id = e.id
            SET m.is_verified = 1,
                m.verified_by = %s,
                m.verified_at = NOW(),
                m.confidence_level = 'HIGH'
            WHERE m.is_verified = 0
            AND LOWER(TRIM(e.name)) COLLATE utf8mb4_unicode_ci = LOWER(TRIM(m.podfactory_name)) COLLATE utf8mb4_unicode_ci
        """, (verified_by,))

        approved_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Bulk verified {approved_count} matching mappings'
        })

    except Exception as e:
        logger.error(f"Error bulk verifying: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/employees/mapping-recommendations', methods=['GET'])
@require_api_key
def get_mapping_recommendations():
    """Get pending PodFactory mappings with recommended employee matches based on name similarity"""
    try:
        from difflib import SequenceMatcher

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get pending mappings (is_verified = 0) that need review
        # These were auto-created during sync and need manager approval
        cursor.execute("""
            SELECT DISTINCT
                m.id as mapping_id,
                m.podfactory_email as user_email,
                m.podfactory_name as user_name,
                m.employee_id as current_employee_id,
                e.name as current_employee_name,
                m.similarity_score as auto_similarity_score,
                m.confidence_level,
                m.created_at
            FROM employee_podfactory_mapping_v2 m
            LEFT JOIN employees e ON m.employee_id = e.id
            WHERE m.is_verified = 0
            AND m.podfactory_email IS NOT NULL
            AND m.podfactory_email != ''
            ORDER BY m.created_at DESC
        """)
        unmapped_pf_users = cursor.fetchall()

        # Get all active employees
        cursor.execute("""
            SELECT id, name, email
            FROM employees
            WHERE is_active = 1
            ORDER BY name
        """)
        employees = cursor.fetchall()

        cursor.close()
        conn.close()

        def calculate_similarity(name1, name2):
            """Calculate similarity score between two names"""
            if not name1 or not name2:
                return 0.0
            name1 = name1.lower().strip()
            name2 = name2.lower().strip()
            return SequenceMatcher(None, name1, name2).ratio()

        def get_recommendations(pf_name, employees, top_n=3):
            """Get top N employee recommendations for a PodFactory name"""
            if not pf_name:
                return []

            scores = []
            for emp in employees:
                emp_name = emp['name']
                score = calculate_similarity(pf_name, emp_name)

                # Also check if first/last names match
                pf_parts = pf_name.lower().split()
                emp_parts = emp_name.lower().split()

                # Boost score if first or last name matches exactly
                for pf_part in pf_parts:
                    for emp_part in emp_parts:
                        if pf_part == emp_part and len(pf_part) > 2:
                            score = min(1.0, score + 0.2)

                if score > 0.3:  # Only include if there's some similarity
                    scores.append({
                        'employee_id': emp['id'],
                        'employee_name': emp['name'],
                        'employee_email': emp['email'],
                        'similarity_score': round(score, 2)
                    })

            # Sort by score descending and return top N
            scores.sort(key=lambda x: x['similarity_score'], reverse=True)
            return scores[:top_n]

        # Build recommendations for each pending mapping
        recommendations = []
        for pf_user in unmapped_pf_users:
            matches = get_recommendations(pf_user['user_name'], employees)

            # Convert datetime to string for JSON serialization
            created_at = pf_user.get('created_at')
            if created_at:
                created_at = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)

            recommendations.append({
                'mapping_id': pf_user['mapping_id'],
                'podfactory_email': pf_user['user_email'],
                'podfactory_name': pf_user['user_name'],
                'current_employee_id': pf_user['current_employee_id'],
                'current_employee_name': pf_user['current_employee_name'],
                'auto_similarity_score': float(pf_user['auto_similarity_score']) if pf_user.get('auto_similarity_score') else 0,
                'confidence_level': pf_user['confidence_level'],
                'created_at': created_at,
                'recommended_matches': matches
            })

        return jsonify({
            'success': True,
            'unmapped_count': len(recommendations),
            'recommendations': recommendations,
            'all_employees': [{'id': e['id'], 'name': e['name']} for e in employees]
        })

    except Exception as e:
        logger.error(f"Error getting mapping recommendations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/employees/create-mapping', methods=['POST'])
@require_api_key
def create_manual_mapping():
    """Create a new employee-to-PodFactory mapping (manual, verified)"""
    try:
        data = request.json
        employee_id = data.get('employee_id')
        podfactory_email = data.get('podfactory_email')
        podfactory_name = data.get('podfactory_name')
        verified_by = data.get('verified_by', 'manager')

        if not employee_id or not podfactory_email:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if mapping already exists
        cursor.execute("""
            SELECT id FROM employee_podfactory_mapping_v2
            WHERE podfactory_email = %s
        """, (podfactory_email,))

        existing = cursor.fetchone()
        if existing:
            # Update existing mapping
            cursor.execute("""
                UPDATE employee_podfactory_mapping_v2
                SET employee_id = %s,
                    podfactory_name = %s,
                    is_verified = 1,
                    verified_by = %s,
                    verified_at = NOW(),
                    confidence_level = 'MANUAL'
                WHERE podfactory_email = %s
            """, (employee_id, podfactory_name, verified_by, podfactory_email))
        else:
            # Create new mapping
            cursor.execute("""
                INSERT INTO employee_podfactory_mapping_v2
                (employee_id, podfactory_email, podfactory_name, similarity_score, confidence_level, is_verified, verified_by, verified_at, created_at)
                VALUES (%s, %s, %s, 1.0, 'MANUAL', 1, %s, NOW(), NOW())
            """, (employee_id, podfactory_email, podfactory_name, verified_by))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Mapping created: {podfactory_email} -> Employee ID {employee_id}'
        })

    except Exception as e:
        logger.error(f"Error creating mapping: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============= UNIFIED NEEDS ATTENTION ENDPOINT =============

@dashboard_bp.route('/employees/needs-attention', methods=['GET'])
@require_api_key
def get_employees_needs_attention():
    """Get unified view of all employees needing attention (Connecteam mapping, pending verifications, etc.)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        result = {
            'success': True,
            'no_connecteam': [],
            'no_podfactory': [],
            'pending_verification': [],
            'summary': {
                'no_connecteam_count': 0,
                'no_podfactory_count': 0,
                'pending_verification_count': 0,
                'total_attention_needed': 0
            }
        }

        # Check if is_contractor column exists
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'employees'
            AND COLUMN_NAME = 'is_contractor'
        """)
        col_check = cursor.fetchone()
        has_contractor_col = col_check['cnt'] > 0 if col_check else False

        # 1. Get employees without Connecteam ID (excluding contractors if column exists)
        if has_contractor_col:
            cursor.execute("""
                SELECT
                    e.id,
                    e.name,
                    e.email,
                    e.is_contractor,
                    GROUP_CONCAT(DISTINCT m.podfactory_email) as podfactory_emails,
                    (SELECT COUNT(*) FROM activity_logs al
                     WHERE al.employee_id = e.id
                     AND al.window_start >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as recent_activity_count
                FROM employees e
                LEFT JOIN employee_podfactory_mapping_v2 m ON e.id = m.employee_id AND m.is_verified = 1
                WHERE e.is_active = 1
                    AND (e.connecteam_user_id IS NULL OR e.connecteam_user_id = '')
                    AND (e.is_contractor IS NULL OR e.is_contractor = 0)
                GROUP BY e.id
                ORDER BY recent_activity_count DESC, e.name
            """)
        else:
            cursor.execute("""
                SELECT
                    e.id,
                    e.name,
                    e.email,
                    0 as is_contractor,
                    GROUP_CONCAT(DISTINCT m.podfactory_email) as podfactory_emails,
                    (SELECT COUNT(*) FROM activity_logs al
                     WHERE al.employee_id = e.id
                     AND al.window_start >= DATE_SUB(NOW(), INTERVAL 30 DAY)) as recent_activity_count
                FROM employees e
                LEFT JOIN employee_podfactory_mapping_v2 m ON e.id = m.employee_id AND m.is_verified = 1
                WHERE e.is_active = 1
                    AND (e.connecteam_user_id IS NULL OR e.connecteam_user_id = '')
                GROUP BY e.id
                ORDER BY recent_activity_count DESC, e.name
            """)
        no_connecteam = cursor.fetchall()

        # Categorize no_connecteam employees
        system_keywords = ['admin', 'factory', 'presser', 'labeler', 'picker', 'printer',
                          'production', 'quality', 'shipper', 'test', 'worker', 'control']

        for emp in no_connecteam:
            name_lower = emp['name'].lower()
            emp['is_system_account'] = any(kw in name_lower for kw in system_keywords)
            emp['category'] = 'system' if emp['is_system_account'] else 'needs_linking'

        result['no_connecteam'] = no_connecteam
        result['summary']['no_connecteam_count'] = len(no_connecteam)

        # 2. Get pending PodFactory verifications
        cursor.execute("""
            SELECT
                m.id as mapping_id,
                m.employee_id,
                e.name as employee_name,
                m.podfactory_email,
                m.podfactory_name,
                m.similarity_score,
                m.confidence_level,
                m.created_at,
                (SELECT COUNT(*) FROM activity_logs al
                 WHERE al.employee_id = m.employee_id
                 AND al.window_start >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as recent_activity_count
            FROM employee_podfactory_mapping_v2 m
            JOIN employees e ON m.employee_id = e.id
            WHERE m.is_verified = 0 AND e.is_active = 1
            ORDER BY m.similarity_score DESC, m.created_at DESC
        """)
        pending = cursor.fetchall()
        result['pending_verification'] = pending
        result['summary']['pending_verification_count'] = len(pending)

        # 3. Get employees with Connecteam but no PodFactory mapping
        cursor.execute("""
            SELECT
                e.id,
                e.name,
                e.email,
                e.connecteam_user_id,
                (SELECT COUNT(*) FROM clock_times ct
                 WHERE ct.employee_id = e.id
                 AND ct.clock_in >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as recent_clock_count
            FROM employees e
            LEFT JOIN employee_podfactory_mapping_v2 m ON e.id = m.employee_id
            WHERE e.is_active = 1
                AND e.connecteam_user_id IS NOT NULL
                AND e.connecteam_user_id != ''
                AND m.id IS NULL
            ORDER BY recent_clock_count DESC, e.name
        """)
        no_podfactory = cursor.fetchall()
        result['no_podfactory'] = no_podfactory
        result['summary']['no_podfactory_count'] = len(no_podfactory)

        result['summary']['total_attention_needed'] = len(no_connecteam) + len(no_podfactory) + len(pending)

        cursor.close()
        conn.close()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting needs-attention: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/podfactory/suggest-emails', methods=['GET'])
@require_api_key
def suggest_podfactory_emails():
    """Search PodFactory database for emails matching employee name"""
    import pymysql

    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    try:
        # Connect to PodFactory database (same server as main DB, different database)
        podfactory_config = {
            'host': os.getenv('DB_HOST', 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com'),
            'port': int(os.getenv('DB_PORT', 25060)),
            'user': os.getenv('DB_USER', 'doadmin'),
            'password': os.getenv('DB_PASSWORD'),
            'database': 'pod-report-stag'
        }

        conn = pymysql.connect(**podfactory_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Split name into parts for searching
        name_parts = name.lower().split()

        if not name_parts:
            return jsonify({'success': True, 'emails': [], 'message': 'Name required'})

        # Build the expected email pattern: firstname.lastnameshp@...
        expected_pattern = '.'.join(name_parts) + 'shp'

        # Query with scoring: exact name match first, then partial matches
        # Score: 3 = exact user_name match, 2 = email starts with expected pattern, 1 = partial match
        conditions = []
        params = []
        for part in name_parts:
            if len(part) >= 2:
                conditions.append("LOWER(user_email) LIKE %s")
                params.append(f"%{part}%")

        if not conditions:
            return jsonify({'success': True, 'emails': [], 'message': 'Name too short'})

        # Add params for scoring
        params_with_scoring = [name.lower(), f"{expected_pattern}%"] + params

        query = f"""
            SELECT DISTINCT user_email, user_name,
                CASE
                    WHEN LOWER(user_name) = %s THEN 3
                    WHEN LOWER(user_email) LIKE %s THEN 2
                    ELSE 1
                END as match_score
            FROM report_actions
            WHERE ({' OR '.join(conditions)})
            AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY match_score DESC, user_email
            LIMIT 5
        """

        cursor.execute(query, params_with_scoring)
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        # Format response
        suggestions = [
            {'email': r['user_email'], 'name': r['user_name']}
            for r in results if r['user_email']
        ]

        return jsonify({
            'success': True,
            'search_name': name,
            'emails': suggestions
        })

    except Exception as e:
        logger.error(f"Error searching PodFactory emails: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/employees/<int:employee_id>/mark-contractor', methods=['POST'])
@require_api_key
def mark_employee_contractor(employee_id):
    """Mark employee as contractor (exempt from Connecteam time tracking)"""
    try:
        data = request.json or {}
        is_contractor = data.get('is_contractor', True)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure is_contractor column exists (use try/except to handle if it already exists)
        try:
            cursor.execute("""
                ALTER TABLE employees ADD COLUMN is_contractor TINYINT(1) DEFAULT 0
            """)
            conn.commit()
        except Exception:
            # Column already exists, that's fine
            pass

        cursor.execute("""
            UPDATE employees
            SET is_contractor = %s
            WHERE id = %s
        """, (1 if is_contractor else 0, employee_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Employee {employee_id} marked as {"contractor" if is_contractor else "regular employee"}'
        })

    except Exception as e:
        logger.error(f"Error marking contractor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@dashboard_bp.route('/bottleneck/test', methods=['GET'])
@require_api_key
def test_bottleneck():
    """Test endpoint for bottleneck detection"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Test 1: Check today's activities
        cursor.execute("""
            SELECT
                activity_type,
                COUNT(*) as count,
                SUM(items_count) as total_items
            FROM activity_logs
            WHERE window_start >= %s AND window_start < %s
                AND source = 'podfactory'
            GROUP BY activity_type
        """, (utc_start, utc_end))
        activities = cursor.fetchall()

        # Test 2: Check active workers
        cursor.execute("""
            SELECT COUNT(*) as active_workers
            FROM clock_times
            WHERE clock_in >= %s AND clock_in < %s
                AND clock_out IS NULL
        """, (utc_start, utc_end))
        workers = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "ok",
            "activities_by_type": activities,
            "active_workers": workers['active_workers'],
            "test_date": get_central_date().strftime('%Y-%m-%d')
        })
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
    
def get_cost_analysis_from_summary(start_date, end_date, db_manager):
    """
    Get cost analysis data from pre-calculated daily_cost_summary table.
    Used for historical queries (not including today) for faster response.

    Returns tuple: (employee_costs, department_costs, qc_passed_items)
    """
    from datetime import datetime
    is_date_range = (start_date != end_date)

    # Query aggregated data from daily_cost_summary
    employee_query = """
    SELECT
        employee_id as id,
        employee_name as name,
        MAX(hourly_rate) as hourly_rate,
        MAX(pay_type) as pay_type,
        SUM(clocked_hours) as clocked_hours,
        SUM(active_hours) as active_hours,
        SUM(non_active_hours) as non_active_hours,
        SUM(total_cost) as total_cost,
        SUM(active_cost) as active_cost,
        SUM(non_active_cost) as non_active_cost,
        SUM(picking_items) as picking_items,
        SUM(labeling_items) as labeling_items,
        SUM(film_matching_items) as film_matching_items,
        SUM(in_production_items) as in_production_items,
        SUM(qc_passed_items) as qc_passed_items,
        SUM(total_items) as items_processed,
        COUNT(DISTINCT summary_date) as days_worked,
        -- Weighted average utilization
        ROUND(SUM(active_hours) / NULLIF(SUM(clocked_hours), 0) * 100, 1) as utilization_rate,
        -- Average efficiency rate
        ROUND(SUM(total_items) / NULLIF(SUM(active_hours) * 60, 0), 3) as efficiency_rate
    FROM daily_cost_summary
    WHERE summary_date BETWEEN %s AND %s
    GROUP BY employee_id, employee_name
    ORDER BY employee_name
    """

    employee_results = db_manager.execute_query(employee_query, (start_date, end_date))

    # Transform to expected format
    employee_costs = []
    for emp in employee_results:
        clocked_hours = float(emp.get('clocked_hours') or 0)
        active_hours = float(emp.get('active_hours') or 0)
        total_cost = float(emp.get('total_cost') or 0)
        active_cost = float(emp.get('active_cost') or 0)
        items_processed = int(emp.get('items_processed') or 0)
        days_worked = int(emp.get('days_worked') or 1)
        utilization = float(emp.get('utilization_rate') or 0)

        emp_data = {
            'id': emp['id'],
            'name': emp['name'],
            'hourly_rate': float(emp.get('hourly_rate') or 13.0),
            'pay_type': emp.get('pay_type', 'hourly'),
            'clocked_hours': round(clocked_hours, 2),
            'active_hours': round(active_hours, 2),
            'non_active_hours': round(float(emp.get('non_active_hours') or 0), 2),
            'total_cost': round(total_cost, 2),
            'active_cost': round(active_cost, 2),
            'non_active_cost': round(float(emp.get('non_active_cost') or 0), 2),
            'items_processed': items_processed,
            'days_worked': days_worked,
            'utilization_rate': utilization,
            'efficiency_rate': float(emp.get('efficiency_rate') or 0),
            'activity_breakdown': {
                'picking': int(emp.get('picking_items') or 0),
                'labeling': int(emp.get('labeling_items') or 0),
                'film_matching': int(emp.get('film_matching_items') or 0),
                'in_production': int(emp.get('in_production_items') or 0),
                'qc_passed': int(emp.get('qc_passed_items') or 0)
            },
            'cost_per_item': round(total_cost / items_processed, 3) if items_processed > 0 else 0,
            'cost_per_item_true': round(total_cost / items_processed, 3) if items_processed > 0 else 0,
            'cost_per_item_active': round(active_cost / items_processed, 3) if items_processed > 0 else 0,
            'efficiency': round(items_processed / total_cost, 1) if total_cost > 0 else 0,
            'active_days': days_worked,
        }

        # Daily averages for date ranges
        if is_date_range:
            emp_data['avg_daily_cost'] = round(total_cost / days_worked, 2) if days_worked > 0 else 0
            emp_data['avg_daily_items'] = round(items_processed / days_worked, 0) if days_worked > 0 else 0
            emp_data['avg_daily_hours'] = round(clocked_hours / days_worked, 1) if days_worked > 0 else 0

        # Status based on utilization
        if utilization >= 70:
            emp_data['status'] = 'EFFICIENT'
            emp_data['status_color'] = '#10b981'
        elif utilization >= 50:
            emp_data['status'] = 'NORMAL'
            emp_data['status_color'] = '#3b82f6'
        elif utilization >= 30:
            emp_data['status'] = 'WATCH'
            emp_data['status_color'] = '#f59e0b'
        else:
            emp_data['status'] = 'IDLE'
            emp_data['status_color'] = '#ef4444'

        employee_costs.append(emp_data)

    # Department costs from summary (simplified - can enhance later if needed)
    department_query = """
    SELECT
        'Production' as department,
        COUNT(DISTINCT employee_id) as employee_count,
        COUNT(DISTINCT summary_date) as days_active,
        SUM(total_items) as items_processed,
        SUM(total_cost) as total_cost
    FROM daily_cost_summary
    WHERE summary_date BETWEEN %s AND %s
    """
    department_costs = db_manager.execute_query(department_query, (start_date, end_date))

    # QC passed items
    qc_passed_items = sum(emp['activity_breakdown']['qc_passed'] for emp in employee_costs)

    return employee_costs, department_costs, qc_passed_items


@dashboard_bp.route('/cost-analysis', methods=['GET'])
@cached_endpoint(ttl_seconds=120)
def get_cost_analysis():
    """Get comprehensive cost analysis data with support for date ranges"""
    try:
        from datetime import datetime, timedelta
        from database.db_manager import get_db
        db_manager = get_db()  # Use singleton, not new instance (avoids 1.7s connection overhead)

        # Support both old 'date' param and new 'start_date'/'end_date' params
        if 'date' in request.args:
            # Old single date format (for backward compatibility)
            start_date = request.args.get('date')
            end_date = start_date
        else:
            # New date range format
            start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
            end_date = request.args.get('end_date', start_date)

        today_str = datetime.now().strftime('%Y-%m-%d')
        is_date_range = (start_date != end_date)
        is_past_only = (end_date < today_str)

        # OPTIMIZATION: Use pre-calculated data for historical queries (not including today)
        if is_past_only:
            logger.info(f"Cost analysis using PRE-CALCULATED data for: {start_date} to {end_date}")
            employee_costs, department_costs, qc_passed_items = get_cost_analysis_from_summary(
                start_date, end_date, db_manager
            )

            # Calculate totals from pre-calculated data
            totals = {
                'active_employees': len(employee_costs),
                'total_clocked_hours': sum(float(emp.get('clocked_hours') or 0) for emp in employee_costs),
                'total_active_hours': sum(float(emp.get('active_hours') or 0) for emp in employee_costs),
                'total_non_active_hours': sum(float(emp.get('non_active_hours') or 0) for emp in employee_costs),
                'total_labor_cost': sum(float(emp.get('total_cost') or 0) for emp in employee_costs),
                'total_active_cost': sum(float(emp.get('active_cost') or 0) for emp in employee_costs),
                'total_non_active_cost': sum(float(emp.get('non_active_cost') or 0) for emp in employee_costs),
                'total_items': sum(emp.get('items_processed', 0) or 0 for emp in employee_costs),
                'avg_hourly_rate': sum(float(emp.get('hourly_rate', 0) or 0) for emp in employee_costs) / len(employee_costs) if employee_costs else 0,
            }

            if totals['total_clocked_hours'] > 0:
                totals['overall_utilization'] = round(totals['total_active_hours'] / totals['total_clocked_hours'] * 100, 1)
            else:
                totals['overall_utilization'] = 0

            top_performers = [emp for emp in employee_costs if emp['items_processed'] > 0]
            top_performers.sort(key=lambda x: x['cost_per_item'])

            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            days_in_range = (end - start).days + 1

            return jsonify({
                'success': True,
                'source': 'pre-calculated',  # Debug marker
                'date_range': {
                    'start': start_date,
                    'end': end_date,
                    'days': days_in_range,
                    'is_range': is_date_range
                },
                'employee_costs': employee_costs,
                'department_costs': department_costs,
                'total_labor_cost': totals['total_labor_cost'],
                'total_active_cost': totals['total_active_cost'],
                'total_non_active_cost': totals['total_non_active_cost'],
                'total_items': totals['total_items'],
                'qc_passed_items': qc_passed_items,
                'total_clocked_hours': totals['total_clocked_hours'],
                'total_active_hours': totals['total_active_hours'],
                'total_non_active_hours': totals['total_non_active_hours'],
                'overall_utilization': totals['overall_utilization'],
                'active_employees': totals['active_employees'],
                'avg_hourly_rate': totals['avg_hourly_rate'],
                'avg_cost_per_item': round(float(totals['total_labor_cost']) / float(qc_passed_items), 3) if qc_passed_items > 0 else 0,
                'avg_cost_per_item_active': round(float(totals['total_active_cost']) / float(qc_passed_items), 3) if qc_passed_items > 0 else 0,
                'daily_avg_cost': round(totals['total_labor_cost'] / days_in_range, 2) if is_date_range else totals['total_labor_cost'],
                'daily_avg_items': round(qc_passed_items / days_in_range, 0) if is_date_range else qc_passed_items,
                'top_performers': top_performers[:5],
                'is_range': is_date_range
            })

        # REAL-TIME CALCULATION: Used when query includes today
        # Get UTC boundaries from request
        utc_start = request.args.get('utc_start')
        utc_end = request.args.get('utc_end')

        # If UTC boundaries not provided, calculate them (fallback)
        if not utc_start or not utc_end:
            # Parse dates
            start_year, start_month, start_day = map(int, start_date.split('-'))
            end_year, end_month, end_day = map(int, end_date.split('-'))

            # Check DST
            is_dst_start = 3 <= start_month <= 11
            is_dst_end = 3 <= end_month <= 11

            offset_start = 5 if is_dst_start else 6
            offset_end = 5 if is_dst_end else 6

            # Calculate UTC boundaries
            utc_start = f"{start_date} {offset_start:02d}:00:00"

            # End date needs next day for boundary (exclusive end for range queries)
            end_next = datetime(end_year, end_month, end_day) + timedelta(days=1)
            utc_end = f"{end_next.strftime('%Y-%m-%d')} {offset_end:02d}:00:00"  # Exclusive end

        is_today_only = (start_date == end_date == today_str)

        # Log for debugging
        logger.info(f"Cost analysis REAL-TIME for: {start_date} to {end_date} (UTC: {utc_start} to {utc_end}, is_today_only: {is_today_only})")

        # Get employee costs for the date range
        # OPTIMIZED: Uses UTC range filter (not CONVERT_TZ) for index usage on clock_times
        # OPTIMIZED: Uses JOINs instead of correlated subqueries
        employee_costs_query = """
        WITH clock_hours AS (
            -- Pre-aggregate clock_times once (filter by UTC range for index usage)
            SELECT
                employee_id,
                SUM(GREATEST(0, TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, UTC_TIMESTAMP())))) / 60.0 as clocked_hours,
                COUNT(DISTINCT DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago'))) as days_worked,
                MIN(clock_in) as first_clock_in
            FROM clock_times
            WHERE clock_in >= %s AND clock_in < %s
            GROUP BY employee_id
        ),
        score_agg AS (
            -- Pre-aggregate daily_scores once
            SELECT
                employee_id,
                SUM(active_minutes) / 60.0 as active_hours,
                SUM(clocked_minutes - active_minutes) / 60.0 as non_active_hours,
                -- Utilization = active_minutes / clocked_minutes (NOT efficiency_rate!)
                LEAST(100, SUM(active_minutes) / NULLIF(SUM(clocked_minutes), 0) * 100) as utilization_rate,
                SUM(items_processed) as items_processed,
                COUNT(DISTINCT score_date) as active_days
            FROM daily_scores
            WHERE score_date BETWEEN %s AND %s
            GROUP BY employee_id
        )
        SELECT
            e.id,
            e.name,
            ep.pay_rate,
            ep.pay_type,
            CASE
                WHEN ep.pay_type = 'salary' THEN ROUND(COALESCE(ep.pay_rate, 13.00 * 8 * 26) / 26 / 8, 2)
                ELSE COALESCE(ep.pay_rate, 13.00)
            END as hourly_rate,
            COALESCE(ch.days_worked, 0) as days_worked,
            ROUND(COALESCE(ch.clocked_hours, 0), 2) as clocked_hours,
            ROUND(COALESCE(sa.active_hours, 0), 2) as active_hours,
            ROUND(GREATEST(0, COALESCE(sa.non_active_hours, ch.clocked_hours - COALESCE(sa.active_hours, 0))), 2) as non_active_hours,
            ROUND(COALESCE(sa.utilization_rate,
                LEAST(100, COALESCE(sa.active_hours, 0) / NULLIF(ch.clocked_hours, 0) * 100)), 1) as utilization_rate,
            ROUND(
                CASE
                    WHEN ep.pay_type = 'salary' THEN (ep.pay_rate / 26) * COALESCE(ch.days_worked, 0)
                    ELSE COALESCE(ch.clocked_hours, 0) * COALESCE(
                        CASE WHEN ep.pay_type = 'salary' THEN ep.pay_rate / 26 / 8 ELSE ep.pay_rate END,
                        13.00)
                END, 2
            ) as total_cost,
            ROUND(COALESCE(sa.active_hours, 0) * COALESCE(
                CASE WHEN ep.pay_type = 'salary' THEN ep.pay_rate / 26 / 8 ELSE ep.pay_rate END,
                13.00), 2) as active_cost,
            ROUND(GREATEST(0, COALESCE(ch.clocked_hours, 0) - COALESCE(sa.active_hours, 0)) * COALESCE(
                CASE WHEN ep.pay_type = 'salary' THEN ep.pay_rate / 26 / 8 ELSE ep.pay_rate END,
                13.00), 2) as non_active_cost,
            COALESCE(sa.items_processed, 0) as items_processed,
            COALESCE(sa.active_days, 0) as active_days
        FROM employees e
        LEFT JOIN employee_payrates ep ON e.id = ep.employee_id
        INNER JOIN clock_hours ch ON e.id = ch.employee_id
        LEFT JOIN score_agg sa ON e.id = sa.employee_id
        WHERE e.is_active = 1
        ORDER BY e.name
        """

        # Optimized params: UTC range for clock_times (uses index), dates for daily_scores
        employee_costs = db_manager.execute_query(
            employee_costs_query,
            (utc_start, utc_end,    # clock_hours CTE (UTC range for index)
            start_date, end_date)   # score_agg CTE (date range)
        )

        # OPTIMIZED: Get activity breakdown for ALL employees in a single batch query (was N+1)
        employee_ids = [emp['id'] for emp in employee_costs]
        if employee_ids:
            # Single query for all employees instead of N queries
            placeholders = ','.join(['%s'] * len(employee_ids))
            activity_breakdown_batch_query = f"""
            SELECT
                employee_id,
                activity_type,
                SUM(items_count) as total_items
            FROM activity_logs
            WHERE employee_id IN ({placeholders})
            AND window_start >= %s
            AND window_start <= %s
            AND source = 'podfactory'
            GROUP BY employee_id, activity_type
            """

            batch_params = employee_ids + [utc_start, utc_end]
            breakdown_results = db_manager.execute_query(activity_breakdown_batch_query, batch_params)

            # Build lookup dictionary by employee_id
            breakdown_by_employee = {}
            for row in breakdown_results:
                emp_id = row['employee_id']
                if emp_id not in breakdown_by_employee:
                    breakdown_by_employee[emp_id] = {
                        'picking': 0,
                        'labeling': 0,
                        'film_matching': 0,
                        'in_production': 0,
                        'qc_passed': 0
                    }
                if row and row['activity_type']:
                    activity_type = row['activity_type'].lower().replace(' ', '_')
                    if activity_type in breakdown_by_employee[emp_id]:
                        breakdown_by_employee[emp_id][activity_type] = row['total_items'] or 0

            # Assign breakdown to each employee
            for emp in employee_costs:
                emp['activity_breakdown'] = breakdown_by_employee.get(emp['id'], {
                    'picking': 0,
                    'labeling': 0,
                    'film_matching': 0,
                    'in_production': 0,
                    'qc_passed': 0
                })
        else:
            # No employees, set empty breakdowns
            for emp in employee_costs:
                emp['activity_breakdown'] = {
                    'picking': 0,
                    'labeling': 0,
                    'film_matching': 0,
                    'in_production': 0,
                    'qc_passed': 0
                }

        # For SINGLE DAY only: Get clock in/out times for tooltip display
        # NOTE: clock_times stores times in UTC, converted to CT for display
        if not is_date_range and employee_ids:
            clock_times_query = """
            SELECT
                ct.employee_id,
                CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago') as clock_in_ct,
                CONVERT_TZ(ct.clock_out, '+00:00', 'America/Chicago') as clock_out_ct,
                GREATEST(0, TIMESTAMPDIFF(MINUTE, ct.clock_in, COALESCE(ct.clock_out, UTC_TIMESTAMP()))) as minutes
            FROM clock_times ct
            WHERE ct.employee_id IN ({})
            AND DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
            ORDER BY ct.clock_in
            """.format(','.join(['%s'] * len(employee_ids)))

            clock_times_params = employee_ids + [start_date]
            clock_times_results = db_manager.execute_query(clock_times_query, clock_times_params)

            # Build lookup by employee_id
            clock_times_by_employee = {}
            for row in clock_times_results:
                emp_id = row['employee_id']
                if emp_id not in clock_times_by_employee:
                    clock_times_by_employee[emp_id] = []
                clock_times_by_employee[emp_id].append({
                    'clock_in': row['clock_in_ct'].strftime('%I:%M %p') if row['clock_in_ct'] else None,
                    'clock_out': row['clock_out_ct'].strftime('%I:%M %p') if row['clock_out_ct'] else 'Active',
                    'minutes': row['minutes']
                })

            # Assign to each employee
            for emp in employee_costs:
                emp['clock_times'] = clock_times_by_employee.get(emp['id'], [])

        # Calculate additional metrics for each employee (rest of the code remains the same)
        for emp in employee_costs:
            try:
                # Use displayed clocked_hours (from daily_scores) for consistent cost calculation
                clocked_hours = float(emp.get('clocked_hours', 0) or 0)
                active_hours = float(emp.get('active_hours', 0) or 0)
                hourly_rate = float(emp.get('hourly_rate', 13.00) or 13.00)

                # Recalculate costs using consistent source (fixes bug where SQL used different data source)
                emp['total_cost'] = round(clocked_hours * hourly_rate, 2)
                emp['active_cost'] = round(active_hours * hourly_rate, 2)
                emp['non_active_cost'] = round((clocked_hours - active_hours) * hourly_rate, 2)

                total_cost = float(emp.get('total_cost', 0) or 0)
                active_cost = float(emp.get('active_cost', 0) or 0)
                items_processed = float(emp.get('items_processed', 0) or 0)
                utilization = float(emp.get('utilization_rate', 0) or 0)
                days_worked = int(emp.get('days_worked', 1) or 1)

                # Cost per item
                emp['cost_per_item'] = round(total_cost / items_processed, 3) if items_processed > 0 else 0
                emp['cost_per_item_true'] = emp['cost_per_item']
                emp['cost_per_item_active'] = round(active_cost / items_processed, 3) if items_processed > 0 else 0
                
                # Daily averages for date ranges
                if is_date_range:
                    emp['avg_daily_cost'] = round(total_cost / days_worked, 2) if days_worked > 0 else 0
                    emp['avg_daily_items'] = round(items_processed / days_worked, 0) if days_worked > 0 else 0
                    emp['avg_daily_hours'] = round(float(emp.get('clocked_hours', 0)) / days_worked, 1) if days_worked > 0 else 0
                
                # Efficiency
                emp['efficiency'] = round((items_processed / total_cost if total_cost != 0 else 0), 1) if total_cost > 0 else 0
                
                # Status based on utilization
                if utilization >= 70:
                    emp['status'] = 'EFFICIENT'
                    emp['status_color'] = '#10b981'
                elif utilization >= 50:
                    emp['status'] = 'NORMAL'
                    emp['status_color'] = '#3b82f6'
                elif utilization >= 30:
                    emp['status'] = 'WATCH'
                    emp['status_color'] = '#f59e0b'
                else:
                    emp['status'] = 'IDLE'
                    emp['status_color'] = '#ef4444'
                    
            except (TypeError, ValueError, ZeroDivisionError) as e:
                logger.error(f"Error calculating metrics for {emp.get('name', 'Unknown')}: {str(e)}")

        # Get department costs for date range - UPDATE TO USE UTC BOUNDARIES
        department_costs_query = """
        SELECT 
            al.department,
            COUNT(DISTINCT al.employee_id) as employee_count,
            COUNT(DISTINCT DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago'))) as days_active,
            SUM(al.items_count) as items_processed,
            ROUND(SUM(
                TIMESTAMPDIFF(SECOND, al.window_start, al.window_end) / 3600.0 *
                CASE 
                    WHEN ep.pay_type = 'salary' THEN COALESCE(ep.pay_rate, 13.00 * 8 * 26) / 26 / 8
                    ELSE ep.pay_rate
                END
            ), 2) as total_cost
        FROM activity_logs al
        JOIN employees e ON al.employee_id = e.id
        LEFT JOIN employee_payrates ep ON e.id = ep.employee_id
        WHERE al.window_start >= %s AND al.window_start <= %s
        AND al.source = 'podfactory'
        GROUP BY al.department
        ORDER BY total_cost DESC
        """
        
        department_costs = db_manager.execute_query(department_costs_query, (utc_start, utc_end))

        # Get QC Passed items for date range - UPDATE TO USE UTC BOUNDARIES
        qc_passed_query = """
        SELECT COALESCE(SUM(items_count), 0) as qc_passed_items
        FROM activity_logs 
        WHERE window_start >= %s AND window_start <= %s
        AND activity_type = 'QC Passed'
        AND source = 'podfactory'
        """
        qc_passed_result = db_manager.execute_query(qc_passed_query, (utc_start, utc_end))
        qc_passed_items = int(qc_passed_result[0]['qc_passed_items']) if qc_passed_result else 0

        # Rest of the function remains the same...
        # Calculate totals
        totals = {
            'active_employees': len(employee_costs),
            'total_clocked_hours': sum(float(emp.get('clocked_hours') or 0) for emp in employee_costs),
            'total_active_hours': sum(float(emp.get('active_hours') or 0) for emp in employee_costs),
            'total_non_active_hours': sum(float(emp.get('non_active_hours') or 0) for emp in employee_costs),
            'total_labor_cost': sum(float(emp.get('total_cost') or 0) for emp in employee_costs),
            'total_active_cost': sum(float(emp.get('active_cost') or 0) for emp in employee_costs),
            'total_non_active_cost': sum(float(emp.get('non_active_cost') or 0) for emp in employee_costs),
            'total_items': sum(emp.get('items_processed', 0) or 0 for emp in employee_costs),
            'total_days': len(set([d for emp in employee_costs for d in range(emp.get('days_worked', 0))])),
            'avg_hourly_rate': sum(float(emp.get('hourly_rate', 0) or 0) for emp in employee_costs) / len(employee_costs) if employee_costs else 0,
        }

        # Calculate utilization
        if totals['total_clocked_hours'] > 0:
            totals['overall_utilization'] = round(totals['total_active_hours'] / totals['total_clocked_hours'] * 100, 1)
        else:
            totals['overall_utilization'] = 0

        # Get top performers
        top_performers = [emp for emp in employee_costs if emp['items_processed'] > 0]
        top_performers.sort(key=lambda x: x['cost_per_item'])
        
        # Calculate date range info
        from datetime import datetime
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days_in_range = (end - start).days + 1
        
        return jsonify({
            'success': True,
            'date_range': {
                'start': start_date,
                'end': end_date,
                'days': days_in_range,
                'is_range': is_date_range
            },
            'employee_costs': employee_costs,
            'department_costs': department_costs,
            'total_labor_cost': totals['total_labor_cost'],
            'total_active_cost': totals['total_active_cost'],
            'total_non_active_cost': totals['total_non_active_cost'],
            'total_items': totals['total_items'],
            'qc_passed_items': qc_passed_items,
            'total_clocked_hours': totals['total_clocked_hours'],
            'total_active_hours': totals['total_active_hours'],
            'total_non_active_hours': totals['total_non_active_hours'],
            'overall_utilization': totals['overall_utilization'],
            'active_employees': totals['active_employees'],
            'avg_hourly_rate': totals['avg_hourly_rate'],
            'avg_cost_per_item': round(float(totals['total_labor_cost']) / float(qc_passed_items), 3) if qc_passed_items > 0 else 0,
            'avg_cost_per_item_active': round(float(totals['total_active_cost']) / float(qc_passed_items), 3) if qc_passed_items > 0 else 0,
            'daily_avg_cost': round(totals['total_labor_cost'] / days_in_range, 2) if is_date_range else totals['total_labor_cost'],
            'daily_avg_items': round(qc_passed_items / days_in_range, 0) if is_date_range else qc_passed_items,
            'top_performers': top_performers[:5],
            'is_range': is_date_range
        })
        
    except Exception as e:
        logger.error(f"Error in cost analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500