"""
User Management API for Admin Panel
Allows admins to manage employee credentials and shop floor access
"""

from flask import Blueprint, request, jsonify
import bcrypt
import secrets
import string
from datetime import datetime
from database.db_manager import get_db
from api.auth import require_api_key

user_management_bp = Blueprint('user_management', __name__)

def hash_pin(pin):
    """Hash PIN using bcrypt (10 rounds)"""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(10)).decode()

def generate_random_pin(length=4):
    """Generate random numeric PIN"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))

@user_management_bp.route('/api/admin/employees', methods=['GET'])
@require_api_key
def list_employees_with_auth():
    """List all employees with their auth status"""
    try:
        employees = get_db().execute_query("""
            SELECT
                e.id,
                e.name,
                e.email,
                e.role,
                e.department,
                e.is_active,
                CASE WHEN ea.pin IS NOT NULL THEN 1 ELSE 0 END as has_pin,
                ea.last_login,
                ea.pin_set_at
            FROM employees e
            LEFT JOIN employee_auth ea ON e.id = ea.employee_id
            ORDER BY e.name
        """)

        return jsonify({
            'success': True,
            'employees': employees or []
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/set-pin', methods=['POST'])
@require_api_key
def set_employee_pin(employee_id):
    """Set or update employee PIN (returns PIN once for print slip)"""
    try:
        data = request.json or {}
        pin = data.get('pin')

        # Auto-generate if not provided
        if not pin:
            pin = generate_random_pin(4)

        # Validate PIN format
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            return jsonify({'success': False, 'message': 'PIN must be 4-6 digits'}), 400

        # Verify employee exists
        employee = get_db().execute_one("""
            SELECT id, name FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        # Hash the PIN
        pin_hash = hash_pin(pin)

        # Check if auth record exists
        existing = get_db().execute_one("""
            SELECT employee_id FROM employee_auth WHERE employee_id = %s
        """, (employee_id,))

        if existing:
            # Update existing record
            get_db().execute_query("""
                UPDATE employee_auth
                SET pin = %s, pin_set_at = NOW()
                WHERE employee_id = %s
            """, (pin_hash, employee_id))
        else:
            # Insert new record
            get_db().execute_query("""
                INSERT INTO employee_auth (employee_id, pin, pin_set_at)
                VALUES (%s, %s, NOW())
            """, (employee_id, pin_hash))

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'pin': pin,  # Only returned once for print slip
            'message': 'PIN set successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/reset-pin', methods=['POST'])
@require_api_key
def reset_employee_pin(employee_id):
    """Reset employee PIN to a new random PIN"""
    try:
        # Verify employee exists
        employee = get_db().execute_one("""
            SELECT id, name FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        # Generate new random PIN
        new_pin = generate_random_pin(4)
        pin_hash = hash_pin(new_pin)

        # Check if auth record exists
        existing = get_db().execute_one("""
            SELECT employee_id FROM employee_auth WHERE employee_id = %s
        """, (employee_id,))

        if existing:
            get_db().execute_query("""
                UPDATE employee_auth
                SET pin = %s, pin_set_at = NOW(), login_token = NULL, token_expires = NULL
                WHERE employee_id = %s
            """, (pin_hash, employee_id))
        else:
            get_db().execute_query("""
                INSERT INTO employee_auth (employee_id, pin, pin_set_at)
                VALUES (%s, %s, NOW())
            """, (employee_id, pin_hash))

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'pin': new_pin,  # Only returned once for print slip
            'message': 'PIN reset successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/toggle-active', methods=['POST'])
@require_api_key
def toggle_employee_active(employee_id):
    """Toggle employee active status"""
    try:
        # Get current status
        employee = get_db().execute_one("""
            SELECT id, name, is_active FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        new_status = 0 if employee['is_active'] else 1

        # Update employee status
        get_db().execute_query("""
            UPDATE employees SET is_active = %s WHERE id = %s
        """, (new_status, employee_id))

        # If deactivating, invalidate their session
        if new_status == 0:
            get_db().execute_query("""
                UPDATE employee_auth
                SET login_token = NULL, token_expires = NULL
                WHERE employee_id = %s
            """, (employee_id,))

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'is_active': bool(new_status),
            'message': f"Employee {'activated' if new_status else 'deactivated'} successfully"
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/revoke-session', methods=['POST'])
@require_api_key
def revoke_employee_session(employee_id):
    """Revoke employee's current session (force logout)"""
    try:
        employee = get_db().execute_one("""
            SELECT id, name FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        get_db().execute_query("""
            UPDATE employee_auth
            SET login_token = NULL, token_expires = NULL
            WHERE employee_id = %s
        """, (employee_id,))

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'message': 'Session revoked successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
