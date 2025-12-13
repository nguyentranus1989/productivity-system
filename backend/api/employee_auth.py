from flask import Blueprint, request, jsonify
import bcrypt
import secrets
from datetime import datetime, timedelta
from database.db_manager import get_db
from utils.timezone_helpers import TimezoneHelper

tz_helper = TimezoneHelper()

employee_auth_bp = Blueprint("employee_auth", __name__)

# PIN hashing functions
def hash_pin(pin):
    """Hash PIN using bcrypt (10 rounds for faster auth)"""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(10)).decode()

def verify_pin(pin, hashed):
    """Verify PIN against bcrypt hash. Also supports legacy plain text for migration."""
    try:
        if hashed and hashed.startswith('$2'):
            return bcrypt.checkpw(pin.encode(), hashed.encode())
        else:
            # Legacy plain text support (will be migrated)
            return pin == hashed
    except Exception:
        return False

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
        
        if not result or not verify_pin(pin, result['pin']):
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Generate session token
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(days=1)
        
        # Update token in database
        get_db().execute_query("""
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
            get_db().execute_query("""
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

@employee_auth_bp.route('/api/employee/change-pin', methods=['POST'])
def change_pin():
    """Allow employee to change their own PIN (requires current PIN)"""
    try:
        # Get employee from token
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        # Verify token and get employee
        employee = get_db().execute_one("""
            SELECT e.id, e.name, ea.pin
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE ea.login_token = %s
            AND ea.token_expires > NOW()
            AND e.is_active = 1
        """, (token,))

        if not employee:
            return jsonify({'success': False, 'message': 'Invalid or expired session'}), 401

        data = request.json
        current_pin = data.get('current_pin')
        new_pin = data.get('new_pin')

        if not current_pin or not new_pin:
            return jsonify({'success': False, 'message': 'Current PIN and new PIN required'}), 400

        # Validate new PIN format (4-6 digits)
        if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 6:
            return jsonify({'success': False, 'message': 'New PIN must be 4-6 digits'}), 400

        # Verify current PIN
        if not verify_pin(current_pin, employee['pin']):
            return jsonify({'success': False, 'message': 'Current PIN is incorrect'}), 401

        # Hash and update new PIN
        new_pin_hash = hash_pin(new_pin)
        get_db().execute_query("""
            UPDATE employee_auth
            SET pin = %s, pin_set_at = NOW()
            WHERE employee_id = %s
        """, (new_pin_hash, employee['id']))

        return jsonify({
            'success': True,
            'message': 'PIN changed successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
