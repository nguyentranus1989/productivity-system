"""
Unified Authentication API
Single login endpoint that detects user type (admin/employee) and routes accordingly.
Maintains security isolation between user types.
"""

from flask import Blueprint, request, jsonify
import bcrypt
import secrets
from datetime import datetime, timedelta
from database.db_manager import get_db
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

unified_auth_bp = Blueprint('unified_auth', __name__)

# Direct DB config for admin (separate from pooled connections for isolation)
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 25060)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME', 'productivity_tracker')
}

def get_admin_db():
    """Separate connection for admin auth (security isolation)"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)

def verify_admin_password(password, hashed):
    """Verify admin password (bcrypt or legacy SHA256)"""
    try:
        if hashed.startswith('$2'):
            return bcrypt.checkpw(password.encode(), hashed.encode())
        else:
            import hashlib
            return hashlib.sha256(password.encode()).hexdigest() == hashed
    except Exception:
        return False

def verify_employee_pin(pin, hashed):
    """Verify employee PIN (bcrypt or legacy plain text)"""
    try:
        if hashed and hashed.startswith('$2'):
            return bcrypt.checkpw(pin.encode(), hashed.encode())
        else:
            return pin == hashed
    except Exception:
        return False


@unified_auth_bp.route('/api/auth/login', methods=['POST'])
def unified_login():
    """
    Unified login endpoint.
    Accepts username/password and determines if user is admin or employee.

    For admins: username is their admin username
    For employees: username is their employee ID (number)

    Returns user_type: 'admin' or 'employee' for frontend routing
    """
    try:
        data = request.get_json()
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', '')).strip()

        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Username and password required'
            }), 400

        # Try admin login first (using separate connection for isolation)
        admin_result = try_admin_login(username, password)
        if admin_result['success']:
            return jsonify(admin_result)

        # If admin failed, try employee login
        employee_result = try_employee_login(username, password)
        if employee_result['success']:
            return jsonify(employee_result)

        # Both failed - generic error message for security
        return jsonify({
            'success': False,
            'message': 'Invalid credentials'
        }), 401

    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Authentication error'
        }), 500


def try_admin_login(username, password):
    """Attempt admin authentication"""
    try:
        conn = get_admin_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, password_hash, full_name, locked_until, failed_attempts
            FROM admin_users
            WHERE username = %s AND is_active = TRUE
        """, (username,))

        admin = cursor.fetchone()

        if not admin:
            cursor.close()
            conn.close()
            return {'success': False}

        # Check if locked
        if admin['locked_until'] and admin['locked_until'] > datetime.now():
            cursor.close()
            conn.close()
            return {'success': False, 'message': 'Account locked. Try again later.'}

        # Verify password
        if not verify_admin_password(password, admin['password_hash']):
            # Increment failed attempts
            cursor.execute("""
                UPDATE admin_users
                SET failed_attempts = failed_attempts + 1,
                    locked_until = CASE
                        WHEN failed_attempts >= 4 THEN DATE_ADD(NOW(), INTERVAL 15 MINUTE)
                        ELSE locked_until
                    END
                WHERE id = %s
            """, (admin['id'],))
            conn.commit()
            cursor.close()
            conn.close()
            return {'success': False}

        # Success - reset failed attempts and generate token
        token = secrets.token_hex(32)
        expires = datetime.now() + timedelta(hours=24)

        cursor.execute("""
            UPDATE admin_users
            SET session_token = %s,
                token_expires = %s,
                failed_attempts = 0,
                last_login = NOW()
            WHERE id = %s
        """, (token, expires, admin['id']))
        conn.commit()

        cursor.close()
        conn.close()

        return {
            'success': True,
            'user_type': 'admin',
            'token': token,
            'user': {
                'id': admin['id'],
                'username': admin['username'],
                'full_name': admin['full_name'] or 'Administrator'
            },
            'redirect': '/manager.html'
        }

    except Exception as e:
        return {'success': False}


def try_employee_login(employee_id, pin):
    """Attempt employee authentication"""
    try:
        # Validate employee_id is numeric
        try:
            emp_id = int(employee_id)
        except ValueError:
            return {'success': False}

        db = get_db()

        result = db.execute_one("""
            SELECT e.id, e.name, ea.pin
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE e.id = %s AND e.is_active = 1
        """, (emp_id,))

        if not result or not verify_employee_pin(pin, result['pin']):
            return {'success': False}

        # Generate token
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(days=1)

        # Update token
        db.execute_update("""
            UPDATE employee_auth
            SET login_token = %s, token_expires = %s, last_login = NOW()
            WHERE employee_id = %s
        """, (token, expires, emp_id))

        return {
            'success': True,
            'user_type': 'employee',
            'token': token,
            'user': {
                'id': result['id'],
                'name': result['name']
            },
            'redirect': '/employee.html'
        }

    except Exception as e:
        return {'success': False}
