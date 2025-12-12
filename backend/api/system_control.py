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
import time
import threading
from functools import wraps
import logging
import platform
import pymysql
import pymysql.cursors

# Add these imports that were missing
from database.db_manager import DatabaseManager, get_db
from config import config

logger = logging.getLogger(__name__)

# Track sync status for async operations
sync_status = {
    'connecteam': {'running': False, 'last_result': None},
    'podfactory': {'running': False, 'last_result': None}
}

# Track recalculation jobs
import uuid
recalc_jobs = {}

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

# Restart service - works on Linux with PM2, limited on Windows
@system_control_bp.route('/api/system/restart-service', methods=['POST'])
@require_admin_auth
def restart_service():
    """Restart a service via PM2 (Linux) or inform user (Windows)"""
    service_name = request.json.get('service')

    if not service_name:
        return jsonify({'success': False, 'error': 'Service name required'}), 400

    if platform.system() == 'Windows':
        # On Windows, we can at least restart the Flask scheduler jobs
        if service_name in ['connecteam-sync', 'podfactory-sync']:
            try:
                # Trigger a sync instead of restart
                sync_type = 'connecteam' if 'connecteam' in service_name else 'podfactory'
                return jsonify({
                    'success': True,
                    'message': f'On Windows: use Force Sync for {sync_type} instead of restart'
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
        else:
            return jsonify({
                'success': False,
                'message': 'Service restart not available on Windows. Use Force Sync buttons instead.'
            })

    # Linux implementation with PM2
    try:
        result = subprocess.run(
            ['pm2', 'restart', service_name],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': f'{service_name} restarted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr or 'PM2 restart failed'
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Restart timeout'}), 500
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'PM2 not found'}), 500
    except Exception as e:
        logger.error(f"Restart service error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@system_control_bp.route('/api/system/force-sync', methods=['POST'])
@require_admin_auth
def force_sync():
    """Force a sync - actually triggers Connecteam or PodFactory sync"""
    sync_type = request.json.get('type', 'connecteam').lower()

    if sync_type not in ['connecteam', 'podfactory']:
        return jsonify({'success': False, 'error': f'Unknown sync type: {sync_type}'}), 400

    # Check if already running
    if sync_status[sync_type]['running']:
        return jsonify({
            'success': False,
            'error': f'{sync_type} sync already in progress'
        }), 409

    try:
        if sync_type == 'connecteam':
            # Import and run Connecteam sync
            from integrations.connecteam_sync import ConnecteamSync

            api_key = config.CONNECTEAM_API_KEY
            clock_id = config.CONNECTEAM_CLOCK_ID

            if not api_key or not clock_id:
                return jsonify({
                    'success': False,
                    'error': 'Connecteam API key or clock ID not configured'
                }), 500

            sync_status['connecteam']['running'] = True
            syncer = ConnecteamSync(api_key, clock_id)

            # Run sync
            result = syncer.sync_todays_shifts()

            sync_status['connecteam']['running'] = False
            sync_status['connecteam']['last_result'] = {
                'timestamp': datetime.now().isoformat(),
                'result': result
            }

            return jsonify({
                'success': True,
                'message': f'Connecteam sync completed',
                'details': result
            })

        else:  # podfactory
            # Import and run PodFactory sync
            from podfactory_sync import PodFactorySync

            sync_status['podfactory']['running'] = True
            syncer = PodFactorySync()

            # Run sync for today
            result = syncer.sync_activities(use_last_sync=False)

            sync_status['podfactory']['running'] = False
            sync_status['podfactory']['last_result'] = {
                'timestamp': datetime.now().isoformat(),
                'result': result
            }

            return jsonify({
                'success': True,
                'message': f'PodFactory sync completed',
                'details': result
            })

    except Exception as e:
        sync_status[sync_type]['running'] = False
        logger.error(f"Force sync error ({sync_type}): {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@system_control_bp.route('/api/system/test-connection', methods=['GET'])
@require_admin_auth
def test_database_connection():
    """Test database connectivity with actual latency measurement"""
    try:
        start_time = time.time()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        latency_ms = round((time.time() - start_time) * 1000, 2)

        return jsonify({
            'success': True,
            'status': 'connected',
            'latency_ms': latency_ms,
            'host': config.DB_HOST,
            'database': config.DB_NAME
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Clear sync logs - actually deletes old log records
@system_control_bp.route('/api/system/clear-sync-logs', methods=['POST'])
@require_admin_auth
def clear_sync_logs():
    """Clear old sync logs from database"""
    sync_type = request.json.get('type', 'connecteam').lower()
    days = request.json.get('days', 7)  # Keep last N days

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if sync_type == 'connecteam':
            # Clear old connecteam sync logs
            cursor.execute("""
                DELETE FROM connecteam_sync_log
                WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            deleted = cursor.rowcount
            conn.commit()

            return jsonify({
                'success': True,
                'message': f'Cleared {deleted} Connecteam sync logs older than {days} days'
            })

        elif sync_type == 'podfactory':
            # Clear old podfactory sync logs (if table exists)
            try:
                cursor.execute("""
                    DELETE FROM podfactory_sync_log
                    WHERE created_at < DATE_SUB(NOW(), INTERVAL %s DAY)
                """, (days,))
                deleted = cursor.rowcount
                conn.commit()
                return jsonify({
                    'success': True,
                    'message': f'Cleared {deleted} PodFactory sync logs older than {days} days'
                })
            except pymysql.err.ProgrammingError:
                # Table doesn't exist
                return jsonify({
                    'success': True,
                    'message': 'No PodFactory sync log table exists'
                })
        else:
            return jsonify({'success': False, 'error': f'Unknown sync type: {sync_type}'}), 400

    except Exception as e:
        logger.error(f"Clear sync logs error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@system_control_bp.route('/api/system/reset-connection-pool', methods=['POST'])
@require_admin_auth
def reset_connection_pool():
    """Reset database connection pool by clearing and recreating connections"""
    try:
        # Get the db manager and reset its pool
        db = get_db()
        if hasattr(db, 'reset_pool'):
            db.reset_pool()
            return jsonify({
                'success': True,
                'message': 'Connection pool reset successfully'
            })
        elif hasattr(db, 'connection_pool'):
            # If using connection pool directly
            db.connection_pool.close()
            return jsonify({
                'success': True,
                'message': 'Connection pool closed and will recreate on next request'
            })
        else:
            # Just verify we can still connect
            conn = get_db_connection()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'Connection verified (no pool to reset)'
            })
    except Exception as e:
        logger.error(f"Reset connection pool error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@system_control_bp.route('/api/system/restart-all', methods=['POST'])
@require_admin_auth
def restart_all_services():
    return jsonify({'success': False, 'message': 'Not available on Windows development'}), 501


@system_control_bp.route('/api/system/logs/<service_name>', methods=['GET'])
@require_admin_auth
def get_service_logs(service_name):
    """Get recent logs for a service"""
    limit = request.args.get('limit', 50, type=int)
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if service_name == 'connecteam':
            cursor.execute("""
                SELECT
                    id,
                    sync_type,
                    status,
                    records_processed,
                    error_message,
                    created_at
                FROM connecteam_sync_log
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))

            logs = cursor.fetchall()
            return jsonify({
                'success': True,
                'service': 'connecteam',
                'logs': [{
                    'id': log['id'],
                    'type': log['sync_type'],
                    'status': log['status'],
                    'records': log['records_processed'],
                    'error': log['error_message'],
                    'timestamp': log['created_at'].isoformat() if log['created_at'] else None
                } for log in logs]
            })

        elif service_name == 'podfactory':
            # Get recent activity logs as proxy for PodFactory sync activity
            cursor.execute("""
                SELECT
                    DATE(created_at) as sync_date,
                    COUNT(*) as items_synced,
                    MIN(created_at) as first_sync,
                    MAX(created_at) as last_sync
                FROM activity_logs
                WHERE scan_type = 'item_scan'
                AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY sync_date DESC
                LIMIT %s
            """, (limit,))

            logs = cursor.fetchall()
            return jsonify({
                'success': True,
                'service': 'podfactory',
                'logs': [{
                    'date': log['sync_date'].isoformat() if log['sync_date'] else None,
                    'items': log['items_synced'],
                    'first': log['first_sync'].isoformat() if log['first_sync'] else None,
                    'last': log['last_sync'].isoformat() if log['last_sync'] else None
                } for log in logs]
            })

        elif service_name == 'flask-backend':
            # Return application info
            return jsonify({
                'success': True,
                'service': 'flask-backend',
                'logs': [{
                    'message': 'Flask backend running',
                    'platform': platform.system(),
                    'python': platform.python_version(),
                    'timestamp': datetime.now().isoformat()
                }]
            })

        else:
            return jsonify({
                'success': False,
                'error': f'Unknown service: {service_name}'
            }), 404

    except Exception as e:
        logger.error(f"Get logs error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============= DATA RECALCULATION =============

def run_recalculation(job_id, start_date, end_date):
    """Background thread to run data recalculation"""
    import time
    job = recalc_jobs[job_id]
    conn = None
    cursor = None
    job['stage_timings'] = {}  # Track per-stage timing
    job_start_time = time.time()

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        stages = [
            ('clock_times.total_minutes', 'Updating clock times total_minutes'),
            ('daily_scores.clocked_minutes', 'Recalculating clocked minutes'),
            ('daily_scores.active_minutes', 'Recalculating active minutes from activity_logs'),
            ('daily_scores.items_processed', 'Recalculating items processed'),
            ('daily_scores.efficiency_rate', 'Recalculating efficiency rates'),
            ('employee_current_status', 'Refreshing employee status view'),
        ]

        job['total_stages'] = len(stages)

        for idx, (stage_id, stage_name) in enumerate(stages):
            stage_start = time.time()
            job['current_stage'] = idx + 1
            job['stage_name'] = stage_name
            job['stage_id'] = stage_id

            if stage_id == 'clock_times.total_minutes':
                # Update total_minutes from clock_in/clock_out
                cursor.execute('''
                    UPDATE clock_times
                    SET total_minutes = GREATEST(0, TIMESTAMPDIFF(MINUTE, clock_in, IFNULL(clock_out, UTC_TIMESTAMP())))
                    WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
                ''', (start_date, end_date))
                job['records_processed'] = cursor.rowcount
                conn.commit()

            elif stage_id == 'daily_scores.clocked_minutes':
                # Get count first
                cursor.execute('''
                    SELECT COUNT(*) as cnt FROM daily_scores
                    WHERE score_date BETWEEN %s AND %s
                ''', (start_date, end_date))
                job['records_total'] = cursor.fetchone()['cnt']

                # Update clocked_minutes from clock_times
                cursor.execute('''
                    UPDATE daily_scores ds
                    SET clocked_minutes = (
                        SELECT COALESCE(SUM(
                            CASE
                                WHEN ct.clock_out IS NOT NULL THEN ct.total_minutes
                                ELSE TIMESTAMPDIFF(MINUTE, ct.clock_in, UTC_TIMESTAMP())
                            END
                        ), 0)
                        FROM clock_times ct
                        WHERE ct.employee_id = ds.employee_id
                        AND DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = ds.score_date
                    )
                    WHERE ds.score_date BETWEEN %s AND %s
                ''', (start_date, end_date))
                job['records_processed'] = cursor.rowcount
                conn.commit()

            elif stage_id == 'daily_scores.active_minutes':
                # Update active_minutes from activity_logs
                cursor.execute('''
                    UPDATE daily_scores ds
                    SET active_minutes = (
                        SELECT COALESCE(SUM(al.duration_minutes), 0)
                        FROM activity_logs al
                        WHERE al.employee_id = ds.employee_id
                        AND DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = ds.score_date
                    )
                    WHERE ds.score_date BETWEEN %s AND %s
                ''', (start_date, end_date))
                job['records_processed'] = cursor.rowcount
                conn.commit()

            elif stage_id == 'daily_scores.items_processed':
                # Update items_processed from activity_logs
                cursor.execute('''
                    UPDATE daily_scores ds
                    SET items_processed = (
                        SELECT COALESCE(SUM(al.items_count), 0)
                        FROM activity_logs al
                        WHERE al.employee_id = ds.employee_id
                        AND DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = ds.score_date
                    )
                    WHERE ds.score_date BETWEEN %s AND %s
                ''', (start_date, end_date))
                job['records_processed'] = cursor.rowcount
                conn.commit()

            elif stage_id == 'daily_scores.efficiency_rate':
                # Calculate efficiency_rate = items / active_minutes
                cursor.execute('''
                    UPDATE daily_scores ds
                    SET efficiency_rate = CASE
                        WHEN active_minutes > 0 THEN ROUND(items_processed / active_minutes, 2)
                        ELSE 0
                    END
                    WHERE ds.score_date BETWEEN %s AND %s
                ''', (start_date, end_date))
                job['records_processed'] = cursor.rowcount
                conn.commit()

            elif stage_id == 'employee_current_status':
                # This is a view/cache table - just mark as done
                job['records_processed'] = 0

            # Record stage timing
            stage_elapsed = round(time.time() - stage_start, 2)
            job['stage_timings'][stage_id] = {
                'elapsed_seconds': stage_elapsed,
                'records': job['records_processed']
            }
            job['elapsed_seconds'] = round(time.time() - job_start_time, 2)
            job['progress_percent'] = int((idx + 1) / len(stages) * 100)

        job['status'] = 'completed'
        job['completed_at'] = datetime.now().isoformat()
        job['total_elapsed_seconds'] = round(time.time() - job_start_time, 2)

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        logger.error(f"Recalculation error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@system_control_bp.route('/api/system/recalculate', methods=['POST'])
@require_admin_auth
def start_recalculation():
    """Start a data recalculation job"""
    data = request.json or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not start_date or not end_date:
        return jsonify({'success': False, 'error': 'start_date and end_date required'}), 400

    # Check if another job is running
    for jid, job in recalc_jobs.items():
        if job.get('status') == 'running':
            return jsonify({
                'success': False,
                'error': 'Another recalculation job is already running',
                'job_id': jid
            }), 409

    # Create new job
    job_id = str(uuid.uuid4())[:8]
    recalc_jobs[job_id] = {
        'job_id': job_id,
        'status': 'running',
        'start_date': start_date,
        'end_date': end_date,
        'current_stage': 0,
        'total_stages': 6,
        'stage_name': 'Initializing...',
        'stage_id': None,
        'progress_percent': 0,
        'records_processed': 0,
        'records_total': 0,
        'started_at': datetime.now().isoformat(),
        'error': None
    }

    # Start background thread
    thread = threading.Thread(target=run_recalculation, args=(job_id, start_date, end_date))
    thread.daemon = True
    thread.start()

    return jsonify({
        'success': True,
        'job_id': job_id,
        'message': 'Recalculation started'
    })


@system_control_bp.route('/api/system/recalculate/status/<job_id>', methods=['GET'])
@require_admin_auth
def get_recalculation_status(job_id):
    """Get status of a recalculation job"""
    if job_id not in recalc_jobs:
        return jsonify({'success': False, 'error': 'Job not found'}), 404

    job = recalc_jobs[job_id]
    return jsonify({
        'success': True,
        **job
    })


@system_control_bp.route('/api/system/recalculate/estimate', methods=['POST'])
@require_admin_auth
def estimate_recalculation():
    """Estimate time for recalculation based on date range"""
    data = request.json or {}
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not start_date or not end_date:
        return jsonify({'success': False, 'error': 'start_date and end_date required'}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Count records that will be affected
        cursor.execute('''
            SELECT COUNT(*) as clock_count FROM clock_times
            WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
        ''', (start_date, end_date))
        clock_count = cursor.fetchone()['clock_count']

        cursor.execute('''
            SELECT COUNT(*) as score_count FROM daily_scores
            WHERE score_date BETWEEN %s AND %s
        ''', (start_date, end_date))
        score_count = cursor.fetchone()['score_count']

        cursor.execute('''
            SELECT COUNT(*) as activity_count FROM activity_logs
            WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) BETWEEN %s AND %s
        ''', (start_date, end_date))
        activity_count = cursor.fetchone()['activity_count']

        # Calculate days
        from datetime import datetime as dt
        d1 = dt.strptime(start_date, '%Y-%m-%d')
        d2 = dt.strptime(end_date, '%Y-%m-%d')
        days = (d2 - d1).days + 1

        # Estimate based on benchmarks (rough: ~1 sec per 10 daily_score records)
        # Plus overhead for activity_logs scans
        base_time = 5  # seconds base overhead
        score_time = score_count * 0.1  # 0.1 sec per daily_score record
        activity_overhead = activity_count * 0.001  # activity_logs scan overhead

        estimated_seconds = base_time + score_time + activity_overhead
        estimated_seconds = max(5, min(estimated_seconds, 1800))  # Cap at 30 min

        return jsonify({
            'success': True,
            'days': days,
            'clock_times_count': clock_count,
            'daily_scores_count': score_count,
            'activity_logs_count': activity_count,
            'estimated_seconds': round(estimated_seconds),
            'estimated_display': format_duration(estimated_seconds)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def format_duration(seconds):
    """Format seconds into human readable duration"""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m"
