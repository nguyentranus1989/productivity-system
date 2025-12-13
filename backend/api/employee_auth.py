from flask import Blueprint, request, jsonify
import secrets
from datetime import datetime, timedelta
from database.db_manager import get_db
from utils.timezone_helpers import TimezoneHelper

tz_helper = TimezoneHelper()

employee_auth_bp = Blueprint("employee_auth", __name__)

@employee_auth_bp.route('/api/employee/login', methods=['POST'])
def employee_login():
    """Authenticate employee with ID and PIN"""
    try:
        data = request.json
        employee_id = data.get('employee_id')
        pin = data.get('pin')
        
        if not employee_id or not pin:
            return jsonify({'success': False, 'message': 'Employee ID and PIN required'}), 400
        
        # Check credentials
        result = get_db().execute_one("""
            SELECT e.id, e.name, ea.pin 
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE e.id = %s AND e.is_active = 1
        """, (employee_id,))
        
        if not result or result['pin'] != pin:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Generate session token
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(days=1)
        
        # Update token in database
        db.execute_query("""
            UPDATE employee_auth 
            SET login_token = %s, token_expires = %s, last_login = NOW()
            WHERE employee_id = %s
        """, (token, expires, employee_id))
        
        return jsonify({
            'success': True,
            'token': token,
            'employee_id': employee_id,
            'name': result['name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/verify', methods=['POST'])
def verify_token():
    """Verify employee session token"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        result = get_db().execute_one("""
            SELECT e.id, e.name 
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE ea.login_token = %s 
            AND ea.token_expires > NOW()
            AND e.is_active = 1
        """, (token,))
        
        if not result:
            return jsonify({'success': False, 'message': 'Invalid or expired token'}), 401
        
        return jsonify({
            'success': True,
            'employee_id': result['id'],
            'name': result['name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/logout', methods=['POST'])
def employee_logout():
    """Logout employee by clearing token"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if token:
            db.execute_query("""
                UPDATE employee_auth 
                SET login_token = NULL, token_expires = NULL
                WHERE login_token = %s
            """, (token,))
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/stats', methods=['GET'])
def get_employee_stats(employee_id):
    """Get performance stats for a specific employee"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        # Get today's stats (using CT date and UTC range)
        stats = get_db().execute_one("""
            SELECT
                e.id,
                e.name,
                COALESCE(ds.items_processed, 0) as items_processed,
                COALESCE(ds.points_earned, 0) as points_earned,
                COALESCE(ds.efficiency_rate, 0) as efficiency,
                COALESCE(ds.active_minutes, 0) as active_minutes,
                COALESCE(
                    TIMESTAMPDIFF(MINUTE,
                        (SELECT MAX(window_end) FROM activity_logs
                         WHERE employee_id = e.id AND window_end >= %s AND window_end < %s),
                        UTC_TIMESTAMP()
                    ), 0
                ) as idle_minutes
            FROM employees e
            LEFT JOIN daily_scores ds ON e.id = ds.employee_id AND ds.score_date = %s
            WHERE e.id = %s
        """, (utc_start, utc_end, ct_date, employee_id))

        if not stats:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        # Get employee rank (using CT date)
        rank_result = get_db().execute_one("""
            SELECT COUNT(*) + 1 as `rank`
            FROM daily_scores
            WHERE score_date = %s
            AND points_earned > (
                SELECT COALESCE(points_earned, 0)
                FROM daily_scores
                WHERE employee_id = %s AND score_date = %s
            )
        """, (ct_date, employee_id, ct_date))

        # Get total active employees today (using UTC range)
        total_result = get_db().execute_one("""
            SELECT COUNT(DISTINCT employee_id) as total
            FROM clock_times
            WHERE clock_in >= %s AND clock_in < %s
        """, (utc_start, utc_end))
        
        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'name': stats['name'],
            'items_processed': stats['items_processed'],
            'points_earned': stats['points_earned'],
            'efficiency': stats['efficiency'],
            'idle_minutes': min(stats['idle_minutes'], 999),  # Cap at 999
            'employee_rank': rank_result['employee_rank'] if rank_result else 999,
            'total_employees': total_result['total'] if total_result else 1
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
