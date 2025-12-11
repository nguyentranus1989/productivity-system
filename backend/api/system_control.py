#!/usr/bin/env python3
"""
System Control API for managing services, syncs, and system health
Location: backend/api/system_control.py
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import subprocess
import json
import os
from functools import wraps
import logging
import platform
import pymysql
import pymysql.cursors

# Add these imports that were missing
from database.db_manager import DatabaseManager
from config import config

logger = logging.getLogger(__name__)

# Add the database connection function
def get_db_connection():
    """Create and return a database connection"""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

# Create blueprint
system_control_bp = Blueprint('system_control', __name__)

# ============= AUTHENTICATION =============
def require_admin_auth(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check API key from header
        api_key = request.headers.get('X-API-Key')
        if api_key != 'dev-api-key-123':  # Update this to your secure key
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Optional: Add admin password check
        admin_password = request.headers.get('X-Admin-Password')
        if admin_password and admin_password != os.environ.get('ADMIN_PASSWORD', 'your-secure-password'):
            return jsonify({'error': 'Invalid admin credentials'}), 403
            
        return f(*args, **kwargs)
    return decorated_function

@system_control_bp.route('/api/system/health', methods=['GET'])
@require_admin_auth
def get_system_health():
    """Get overall system health status"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        health = {
            'timestamp': datetime.now().isoformat(),
            'syncs': {},
            'services': {},
            'database': {'status': 'unknown'}
        }
        
        # Check Connecteam sync - FIXED: changed to 'shifts' instead of 'time_entries'
        cursor.execute("""
            SELECT 
                sync_type,
                MAX(status) as status,
                MAX(created_at) as last_sync,
                TIMESTAMPDIFF(MINUTE, MAX(created_at), NOW()) as minutes_ago,
                COUNT(*) as sync_count
            FROM connecteam_sync_log
            WHERE sync_type = 'shifts'
            AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
            GROUP BY sync_type
            ORDER BY MAX(created_at) DESC
            LIMIT 1
        """)
        
        connecteam = cursor.fetchone()
        # Consume any remaining results
        while cursor.nextset():
            pass
        
        if connecteam:
            health['syncs']['connecteam'] = {
                'status': 'healthy' if connecteam['minutes_ago'] < 10 else 
                          'warning' if connecteam['minutes_ago'] < 30 else 'critical',
                'last_sync': connecteam['last_sync'].isoformat() if connecteam['last_sync'] else None,
                'minutes_ago': connecteam['minutes_ago'],
                'records': connecteam['sync_count']
            }
        
        # Check PodFactory sync - with proper error handling
        try:
            cursor.execute("""
                SELECT 
                    'podfactory' as sync_type,
                    MAX(created_at) as last_sync,
                    TIMESTAMPDIFF(MINUTE, MAX(created_at), NOW()) as minutes_ago,
                    COUNT(*) as items_count
                FROM activity_logs
                WHERE scan_type = 'item_scan'
                AND created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """)
            
            podfactory = cursor.fetchone()
            # Consume any remaining results
            while cursor.nextset():
                pass
                
            if podfactory and podfactory['last_sync']:
                health['syncs']['podfactory'] = {
                    'status': 'healthy' if podfactory['minutes_ago'] < 60 else 
                              'warning' if podfactory['minutes_ago'] < 120 else 'critical',
                    'last_sync': podfactory['last_sync'].isoformat() if podfactory['last_sync'] else None,
                    'minutes_ago': podfactory['minutes_ago'] or 999,
                    'items': podfactory['items_count']
                }
            else:
                health['syncs']['podfactory'] = {
                    'status': 'unknown',
                    'last_sync': None,
                    'minutes_ago': 999,
                    'items': 0
                }
        except Exception as e:
            print(f"Error checking PodFactory sync: {e}")
            health['syncs']['podfactory'] = {
                'status': 'unknown',
                'last_sync': None,
                'minutes_ago': 999,
                'items': 0
            }
        
        # Check database connection
        cursor.execute("SELECT 1")
        cursor.fetchone()
        health['database']['status'] = 'connected'
        
        # Show services status
        health['services']['flask-backend'] = {'status': 'online'}
        
        return jsonify(health)
        
    except Exception as e:
        print(f"Error getting system health: {e}")
        return jsonify({
            'error': 'Failed to get system health',
            'timestamp': datetime.now().isoformat()
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@system_control_bp.route('/api/system/pm2-status', methods=['GET'])
@require_admin_auth  
def get_pm2_status():
    """Get PM2 process status"""
    try:
        # Check if we're on Windows
        if platform.system() == 'Windows':
            return jsonify({
                'success': True,
                'processes': [
                    {
                        'name': 'flask-backend',
                        'status': 'online',
                        'uptime': 'N/A (Windows)',
                        'memory': 0,
                        'restarts': 0
                    }
                ],
                'message': 'PM2 not available on Windows'
            })
        
        # Original PM2 code for Linux...
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout:
            processes_data = json.loads(result.stdout)
            processes = []
            
            for p in processes_data:
                process_info = {
                    'name': p.get('name', 'Unknown'),
                    'status': p.get('pm2_env', {}).get('status', 'unknown'),
                    'memory': p.get('monit', {}).get('memory', 0),
                    'uptime': p.get('pm2_env', {}).get('pm_uptime', 0),
                    'restarts': p.get('pm2_env', {}).get('restart_time', 0)
                }
                processes.append(process_info)
            
            return jsonify({'success': True, 'processes': processes})
        else:
            return jsonify({'success': False, 'error': 'Failed to get PM2 status'}), 500
            
    except Exception as e:
        print(f"Error getting PM2 status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add stub functions for other endpoints (implement later as needed)
@system_control_bp.route('/api/system/restart-service', methods=['POST'])
@require_admin_auth
def restart_service():
    """Restart a service (stub for Windows)"""
    service_name = request.json.get('service')
    
    if platform.system() == 'Windows':
        return jsonify({
            'success': False,
            'message': f'Service restart not available on Windows development'
        })
    
    # Linux implementation would go here
    return jsonify({'success': False, 'error': 'Not implemented'}), 501

@system_control_bp.route('/api/system/force-sync', methods=['POST'])
@require_admin_auth
def force_sync():
    """Force a sync (stub)"""
    return jsonify({
        'success': True,
        'message': 'Sync triggered (simulated for development)'
    })

@system_control_bp.route('/api/system/test-connection', methods=['GET'])
@require_admin_auth
def test_database_connection():
    """Test database connectivity"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'status': 'connected',
            'latency_ms': 50  # Simulated for now
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add remaining stub endpoints
@system_control_bp.route('/api/system/clear-sync-logs', methods=['POST'])
@require_admin_auth
def clear_sync_logs():
    return jsonify({'success': True, 'message': 'Logs cleared (simulated)'})

@system_control_bp.route('/api/system/reset-connection-pool', methods=['POST'])
@require_admin_auth  
def reset_connection_pool():
    return jsonify({'success': True, 'message': 'Connection pool reset (simulated)'})

@system_control_bp.route('/api/system/restart-all', methods=['POST'])
@require_admin_auth
def restart_all_services():
    return jsonify({'success': False, 'message': 'Not available on Windows development'}), 501
