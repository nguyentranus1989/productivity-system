"""
User Management API for Admin Panel
Allows admins to manage employee credentials and shop floor access
"""

from flask import Blueprint, request, jsonify
import bcrypt
import secrets
import string
import threading
from datetime import datetime
from database.db_manager import get_db
from api.auth import require_api_key
from services.email_service import EmailService
from integrations.auth0_manager import Auth0Manager


def send_email_async(employee_id, employee_name, pin, personal_email):
    """Send welcome email in background thread"""
    def _send():
        try:
            result = EmailService.send_welcome_email(employee_name, pin, personal_email, employee_id)
            if result['success']:
                # Update welcome_sent_at in database
                get_db().execute_query("""
                    UPDATE employees SET welcome_sent_at = NOW() WHERE id = %s
                """, (employee_id,))
                print(f"[Email] Welcome email sent to {personal_email}")
            else:
                print(f"[Email] Failed to send: {result['message']}")
        except Exception as e:
            print(f"[Email] Error: {str(e)}")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()

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
                e.personal_email,
                e.phone_number,
                rc.role_name as role,
                e.role_id as local_role_id,
                e.is_active,
                CASE WHEN ea.pin IS NOT NULL THEN 1 ELSE 0 END as has_pin,
                ea.pin_plain,
                ea.last_login,
                ea.pin_set_at,
                e.welcome_sent_at,
                e.auth0_user_id,
                e.workspace
            FROM employees e
            LEFT JOIN role_configs rc ON e.role_id = rc.id
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
        send_notification = data.get('send_notification', False)

        # Auto-generate if not provided
        if not pin:
            pin = generate_random_pin(4)

        # Validate PIN format
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            return jsonify({'success': False, 'message': 'PIN must be 4-6 digits'}), 400

        # Verify employee exists and get contact info
        employee = get_db().execute_one("""
            SELECT id, name, personal_email FROM employees WHERE id = %s
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
            # Update existing record (store both hash and plain for export)
            get_db().execute_query("""
                UPDATE employee_auth
                SET pin = %s, pin_plain = %s, pin_set_at = NOW()
                WHERE employee_id = %s
            """, (pin_hash, pin, employee_id))
        else:
            # Insert new record
            get_db().execute_query("""
                INSERT INTO employee_auth (employee_id, pin, pin_plain, pin_set_at)
                VALUES (%s, %s, %s, NOW())
            """, (employee_id, pin_hash, pin))

        # Send notification if requested (async to avoid timeout)
        email_queued = False
        if send_notification and employee.get('personal_email'):
            send_email_async(employee_id, employee['name'], pin, employee['personal_email'])
            email_queued = True

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'pin': pin,  # Only returned once for print slip
            'message': 'PIN set successfully',
            'notification': {'queued': email_queued} if email_queued else None
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/reset-pin', methods=['POST'])
@require_api_key
def reset_employee_pin(employee_id):
    """Reset employee PIN to a new random PIN"""
    try:
        data = request.json or {}
        send_notification = data.get('send_notification', False)

        # Verify employee exists
        employee = get_db().execute_one("""
            SELECT id, name, personal_email FROM employees WHERE id = %s
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
                SET pin = %s, pin_plain = %s, pin_set_at = NOW(), login_token = NULL, token_expires = NULL
                WHERE employee_id = %s
            """, (pin_hash, new_pin, employee_id))
        else:
            get_db().execute_query("""
                INSERT INTO employee_auth (employee_id, pin, pin_plain, pin_set_at)
                VALUES (%s, %s, %s, NOW())
            """, (employee_id, pin_hash, new_pin))

        # Send notification if requested (async to avoid timeout)
        email_queued = False
        if send_notification and employee.get('personal_email'):
            send_email_async(employee_id, employee['name'], new_pin, employee['personal_email'])
            email_queued = True

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'pin': new_pin,  # Only returned once for print slip
            'message': 'PIN reset successfully',
            'notification': {'queued': email_queued} if email_queued else None
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

@user_management_bp.route('/api/admin/employees/export-pins', methods=['GET'])
@require_api_key
def export_employee_pins():
    """Export all employees with their PINs as CSV"""
    try:
        employees = get_db().execute_query("""
            SELECT
                e.id,
                e.name,
                rc.role_name as role,
                ea.pin_plain as pin,
                ea.pin_set_at
            FROM employees e
            LEFT JOIN role_configs rc ON e.role_id = rc.id
            LEFT JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE e.is_active = 1
            ORDER BY e.name
        """)

        # Build CSV
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Employee ID', 'Name', 'Role', 'PIN', 'PIN Set Date'])
        for emp in employees:
            writer.writerow([
                emp['id'],
                emp['name'],
                emp['role'] or '',
                emp['pin'] or 'NOT SET',
                emp['pin_set_at'].strftime('%Y-%m-%d %H:%M') if emp['pin_set_at'] else ''
            ])

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=employee_pins.csv'}
        )

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/bulk-generate-pins', methods=['POST'])
@require_api_key
def bulk_generate_pins():
    """Generate PINs for all employees without one"""
    try:
        # Get employees without PINs
        employees = get_db().execute_query("""
            SELECT e.id, e.name
            FROM employees e
            LEFT JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE e.is_active = 1 AND (ea.pin IS NULL OR ea.pin = '')
        """)

        if not employees:
            return jsonify({'success': True, 'message': 'All employees already have PINs', 'count': 0})

        generated = []
        for emp in employees:
            pin = generate_random_pin(4)
            pin_hash = hash_pin(pin)

            # Check if auth record exists
            existing = get_db().execute_one(
                "SELECT employee_id FROM employee_auth WHERE employee_id = %s",
                (emp['id'],)
            )

            if existing:
                get_db().execute_query("""
                    UPDATE employee_auth
                    SET pin = %s, pin_plain = %s, pin_set_at = NOW()
                    WHERE employee_id = %s
                """, (pin_hash, pin, emp['id']))
            else:
                get_db().execute_query("""
                    INSERT INTO employee_auth (employee_id, pin, pin_plain, pin_set_at)
                    VALUES (%s, %s, %s, NOW())
                """, (emp['id'], pin_hash, pin))

            generated.append({'id': emp['id'], 'name': emp['name'], 'pin': pin})

        return jsonify({
            'success': True,
            'message': f'Generated PINs for {len(generated)} employees',
            'count': len(generated),
            'employees': generated
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/update-contact', methods=['POST'])
@require_api_key
def update_employee_contact(employee_id):
    """Update employee's personal email and phone number"""
    try:
        data = request.json or {}
        personal_email = data.get('personal_email', '').strip() or None
        phone_number = data.get('phone_number', '').strip() or None

        # Verify employee exists
        employee = get_db().execute_one("""
            SELECT id, name FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        # Update contact info
        get_db().execute_query("""
            UPDATE employees
            SET personal_email = %s, phone_number = %s
            WHERE id = %s
        """, (personal_email, phone_number, employee_id))

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'personal_email': personal_email,
            'phone_number': phone_number,
            'message': 'Contact info updated successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@user_management_bp.route('/api/admin/employees/<int:employee_id>/send-welcome', methods=['POST'])
@require_api_key
def send_welcome_notification(employee_id):
    """Send welcome email with current PIN to employee"""
    try:
        # Get employee with PIN
        employee = get_db().execute_one("""
            SELECT e.id, e.name, e.personal_email, ea.pin_plain
            FROM employees e
            LEFT JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE e.id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        if not employee.get('personal_email'):
            return jsonify({'success': False, 'message': 'Employee has no personal email set'}), 400

        if not employee.get('pin_plain'):
            return jsonify({'success': False, 'message': 'Employee has no PIN set. Set PIN first.'}), 400

        # Send email
        result = EmailService.send_welcome_email(
            employee['name'],
            employee['pin_plain'],
            employee['personal_email'],
            employee_id
        )

        if result['success']:
            get_db().execute_query("""
                UPDATE employees SET welcome_sent_at = NOW() WHERE id = %s
            """, (employee_id,))

        return jsonify({
            'success': result['success'],
            'message': result['message'],
            'employee_id': employee_id
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== Auth0 Integration Endpoints ====================

@user_management_bp.route('/api/admin/auth0/roles', methods=['GET'])
@require_api_key
def get_auth0_roles():
    """Get available Auth0 roles for dropdown"""
    try:
        result = Auth0Manager.get_roles()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'roles': []}), 500


@user_management_bp.route('/api/admin/auth0/workspaces', methods=['GET'])
@require_api_key
def get_auth0_workspaces():
    """Get available workspaces for dropdown"""
    try:
        workspaces = Auth0Manager.get_workspaces()
        return jsonify({'success': True, 'workspaces': workspaces})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'workspaces': []}), 500


@user_management_bp.route('/api/admin/employees/create', methods=['POST'])
@require_api_key
def create_employee_with_auth0():
    """Create new employee with Auth0 account"""
    try:
        data = request.json or {}

        # Required fields
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()

        if not name or not email:
            return jsonify({'success': False, 'message': 'Name and email are required'}), 400

        # Optional fields
        role_id = data.get('role_id')  # Auth0 role ID
        workspace = data.get('workspace') or 'MS'  # Default Mississippi
        personal_email = (data.get('personal_email') or '').strip() or None
        phone_number = (data.get('phone_number') or '').strip() or None
        local_role_id = data.get('local_role_id')  # Local role_configs.id

        # Check if email already exists
        existing = get_db().execute_one(
            "SELECT id FROM employees WHERE email = %s", (email,)
        )
        if existing:
            return jsonify({'success': False, 'message': 'Employee with this email already exists'}), 409

        # Create Auth0 account first
        auth0_result = Auth0Manager.create_user({
            'name': name,
            'email': email,
            'role_id': role_id,
            'workspace': workspace
        })

        if not auth0_result['success']:
            return jsonify({
                'success': False,
                'message': f"Auth0 account creation failed: {auth0_result['message']}"
            }), 500

        # Create local employee record
        try:
            get_db().execute_query("""
                INSERT INTO employees (name, email, personal_email, phone_number, role_id, is_active, auth0_user_id, workspace, created_at)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s, NOW())
            """, (name, email, personal_email, phone_number, local_role_id, auth0_result['user_id'], workspace))

            # Get the new employee ID
            new_employee = get_db().execute_one(
                "SELECT id FROM employees WHERE email = %s", (email,)
            )
            employee_id = new_employee['id'] if new_employee else None

            return jsonify({
                'success': True,
                'employee_id': employee_id,
                'auth0_user_id': auth0_result['user_id'],
                'password': auth0_result['password'],  # Show once for admin to share
                'message': 'Employee created with Auth0 account'
            })

        except Exception as db_error:
            # Rollback: Delete Auth0 user if local insert fails
            Auth0Manager.delete_user(auth0_result['user_id'])
            raise db_error

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@user_management_bp.route('/api/admin/employees/<int:employee_id>/delete', methods=['DELETE'])
@require_api_key
def delete_employee_with_auth0(employee_id):
    """Delete employee and their Auth0 account"""
    try:
        # Get employee with Auth0 info
        employee = get_db().execute_one("""
            SELECT id, name, auth0_user_id FROM employees WHERE id = %s
        """, (employee_id,))

        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        auth0_result = {'success': True, 'message': 'No Auth0 account'}

        # Delete Auth0 account if exists
        if employee.get('auth0_user_id'):
            auth0_result = Auth0Manager.delete_user(employee['auth0_user_id'])

        # Delete local records (auth first, then employee)
        get_db().execute_query(
            "DELETE FROM employee_auth WHERE employee_id = %s", (employee_id,)
        )
        get_db().execute_query(
            "DELETE FROM employees WHERE id = %s", (employee_id,)
        )

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'auth0_deleted': auth0_result['success'],
            'message': 'Employee deleted successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
