"""
Admin Authentication API for Warehouse Productivity System
"""

from flask import Blueprint, request, jsonify
import hashlib
import secrets
import pymysql
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

admin_auth_bp = Blueprint('admin_auth', __name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com'),
    'port': int(os.getenv('DB_PORT', 25060)),
    'user': os.getenv('DB_USER', 'doadmin'),
    'password': os.getenv('DB_PASSWORD', 'AVNS_OWqdUdZ2Nw_YCkGI5Eu'),
    'database': os.getenv('DB_NAME', 'productivity_tracker')
}

def get_db_connection():
    """Create database connection"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    """Generate secure random token"""
    return secrets.token_hex(32)

@admin_auth_bp.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Admin login endpoint"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM admin_users 
            WHERE username = %s AND is_active = TRUE
        """, (username,))
        
        admin = cursor.fetchone()
        
        if not admin:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        if admin['locked_until'] and admin['locked_until'] > datetime.now():
            return jsonify({'success': False, 'message': 'Account locked. Try again later.'}), 401
        
        password_hash = hash_password(password)
        if admin['password_hash'] != password_hash:
            cursor.execute("""
                UPDATE admin_users 
                SET failed_attempts = failed_attempts + 1,
                    locked_until = IF(failed_attempts >= 4, DATE_ADD(NOW(), INTERVAL 30 MINUTE), NULL)
                WHERE id = %s
            """, (admin['id'],))
            conn.commit()
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        token = generate_token()
        expires = datetime.now() + timedelta(hours=4)
        
        cursor.execute("""
            UPDATE admin_users 
            SET session_token = %s,
                token_expires = %s,
                last_login = NOW(),
                failed_attempts = 0,
                locked_until = NULL
            WHERE id = %s
        """, (token, expires, admin['id']))
        
        ip_address = request.remote_addr
        cursor.execute("""
            INSERT INTO admin_audit_log (admin_id, action, details, ip_address)
            VALUES (%s, 'LOGIN', %s, %s)
        """, (admin['id'], f"Admin {username} logged in", ip_address))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'token': token,
            'username': username,
            'full_name': admin['full_name'],
            'expires': expires.isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Login failed: {str(e)}'}), 500

@admin_auth_bp.route('/api/admin/verify', methods=['POST'])
def verify_admin():
    """Verify admin session token"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()
        
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, full_name, token_expires 
            FROM admin_users 
            WHERE session_token = %s AND is_active = TRUE
        """, (token,))
        
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not admin:
            return jsonify({'success': False, 'message': 'Invalid session'}), 401
        
        if admin['token_expires'] < datetime.now():
            return jsonify({'success': False, 'message': 'Session expired'}), 401
        
        return jsonify({
            'success': True,
            'username': admin['username'],
            'full_name': admin['full_name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Verification failed: {str(e)}'}), 500

@admin_auth_bp.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    """Admin logout endpoint"""
    try:
        data = request.get_json()
        token = data.get('token', '').strip()
        
        if token:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, username FROM admin_users WHERE session_token = %s", (token,))
            admin = cursor.fetchone()
            
            if admin:
                cursor.execute("""
                    UPDATE admin_users 
                    SET session_token = NULL, token_expires = NULL 
                    WHERE session_token = %s
                """, (token,))
                
                cursor.execute("""
                    INSERT INTO admin_audit_log (admin_id, action, details, ip_address)
                    VALUES (%s, 'LOGOUT', %s, %s)
                """, (admin['id'], f"Admin {admin['username']} logged out", request.remote_addr))
                
                conn.commit()
            
            cursor.close()
            conn.close()
        
        return jsonify({'success': True, 'message': 'Logged out successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Logout failed: {str(e)}'}), 500
