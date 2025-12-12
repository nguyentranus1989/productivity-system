# backend/api/connecteam.py

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

# LAZY IMPORT: ConnecteamSync moved inside get_sync_service() for fast startup
from config import config
from api.auth import require_api_key
from api.validators import validate_date

logger = logging.getLogger(__name__)

connecteam_bp = Blueprint('connecteam', __name__)

# Lazy-loaded sync service
_sync_service = None

def get_sync_service():
    """Get sync service instance (lazy initialization)"""
    global _sync_service
    if _sync_service is None:
        # Import here to avoid slow startup (connecteam_sync imports heavy deps)
        from integrations.connecteam_sync import ConnecteamSync
        _sync_service = ConnecteamSync(
            config.CONNECTEAM_API_KEY,
            config.CONNECTEAM_CLOCK_ID
        )
    return _sync_service


@connecteam_bp.route('/sync/employees', methods=['POST'])
@require_api_key
def sync_employees():
    """Sync employees from Connecteam"""
    try:
        stats = get_sync_service().sync_employees()
        
        return jsonify({
            'success': True,
            'message': 'Employee sync completed',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in employee sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/sync/shifts/today', methods=['POST'])
@require_api_key
def sync_todays_shifts():
    """Sync today's shifts from Connecteam"""
    try:
        stats = get_sync_service().sync_todays_shifts()
        
        return jsonify({
            'success': True,
            'message': 'Shift sync completed',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in shift sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/sync/historical', methods=['POST'])
@require_api_key
def sync_historical():
    """Sync historical shift data"""
    try:
        days_back = request.json.get('days_back', 30)
        
        if not isinstance(days_back, int) or days_back < 1 or days_back > 365:
            return jsonify({
                'success': False,
                'error': 'days_back must be between 1 and 365'
            }), 400
        
        stats = get_sync_service().sync_historical_data(days_back)
        
        return jsonify({
            'success': True,
            'message': f'Historical sync completed for {days_back} days',
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error in historical sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/working/today', methods=['GET'])
@require_api_key
def get_working_today():
    """Get list of employees working today (Redis cached, 5-min TTL)"""
    import json as json_module
    try:
        sync_service = get_sync_service()

        # Try cache first (5-minute TTL)
        cached = sync_service.cache.get('working_today')
        if cached:
            cache_data = json_module.loads(cached)
            working_today = cache_data.get('employees', [])
            logger.debug(f"Cache HIT for working_today: {len(working_today)} employees")
        else:
            logger.debug("Cache MISS for working_today - fetching from Connecteam API")
            # Get fresh data from Connecteam API
            shifts = sync_service.client.get_todays_shifts()
            working_today = []

            for shift in shifts:
                employee = sync_service._get_employee_by_connecteam_id(shift.user_id)
                if employee:
                    working_today.append({
                        'employee_id': employee['id'],
                        'name': shift.employee_name,
                        'title': shift.title,
                        'role': 'Worker',
                        'clock_in': shift.clock_in.isoformat(),
                        'clock_out': shift.clock_out.isoformat() if shift.clock_out else None,
                        'total_minutes': round(shift.total_minutes, 1),
                        'is_active': shift.is_active,
                        'status': 'Working' if shift.is_active else 'Completed'
                    })

            # Cache the results with 5-minute TTL
            cache_data = {
                'employees': working_today,
                'timestamp': datetime.now().isoformat()
            }
            sync_service.cache.set('working_today', json_module.dumps(cache_data), ttl=300)
            logger.info(f"Cached working_today: {len(working_today)} employees (TTL: 300s)")

        # Summary stats
        total_working = len(working_today)
        currently_active = sum(1 for e in working_today if e.get('is_active'))
        
        return jsonify({
            'success': True,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'summary': {
                'total_employees': total_working,
                'currently_active': currently_active,
                'completed_shifts': total_working - currently_active
            },
            'employees': working_today
        })
        
    except Exception as e:
        logger.error(f"Error getting working today: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/working/now', methods=['GET'])
@require_api_key
def get_currently_working():
    """Get employees currently clocked in (Redis cached, 5-min TTL)"""
    import json as json_module
    try:
        sync_service = get_sync_service()

        # Try cache first (5-minute TTL)
        cached = sync_service.cache.get('currently_working')
        if cached:
            cache_data = json_module.loads(cached)
            currently_working = cache_data.get('employees', [])
            logger.debug(f"Cache HIT for currently_working: {len(currently_working)} employees")
        else:
            logger.debug("Cache MISS for currently_working - fetching from Connecteam API")
            # Get fresh data from Connecteam API
            shifts = sync_service.client.get_currently_working()
            currently_working = []

            for shift in shifts:
                employee = sync_service._get_employee_by_connecteam_id(shift.user_id)
                if employee:
                    currently_working.append({
                        'employee_id': employee['id'],
                        'name': shift.employee_name,
                        'title': shift.title,
                        'role': 'Worker',
                        'clock_in': shift.clock_in.isoformat(),
                        'duration_minutes': round(shift.total_minutes, 1),
                        'duration_hours': round(shift.total_minutes / 60, 1)
                    })

            # Cache the results with 5-minute TTL
            cache_data = {
                'employees': currently_working,
                'timestamp': datetime.now().isoformat()
            }
            sync_service.cache.set('currently_working', json_module.dumps(cache_data), ttl=300)
            logger.info(f"Cached currently_working: {len(currently_working)} employees (TTL: 300s)")

        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'count': len(currently_working),
            'employees': currently_working
        })
        
    except Exception as e:
        logger.error(f"Error getting currently working: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/employee/<int:employee_id>/live-minutes', methods=['GET'])
@require_api_key
def get_employee_live_minutes(employee_id):
    """Get live clocked minutes for specific employee"""
    try:
        minutes = get_sync_service().get_live_clocked_minutes(employee_id)
        
        if minutes is None:
            return jsonify({
                'success': False,
                'error': 'Employee not currently clocked in'
            }), 404
        
        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'total_minutes': round(minutes, 1),
            'total_hours': round(minutes / 60, 1),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting live minutes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/shifts/<date>', methods=['GET'])
@require_api_key
def get_shifts_by_date(date):
    """Get all shifts for a specific date"""
    try:
        # Validate date
        if not validate_date(date):
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        shifts = get_sync_service().client.get_shifts_for_date(date)
        
        shift_data = []
        for shift in shifts:
            employee = get_sync_service()._get_employee_by_connecteam_id(shift.user_id)
            
            shift_info = {
                'connecteam_user_id': shift.user_id,
                'employee_name': shift.employee_name,
                'title': shift.title,
                'clock_in': shift.clock_in.isoformat(),
                'clock_out': shift.clock_out.isoformat() if shift.clock_out else None,
                'total_minutes': round(shift.total_minutes, 1) if shift.total_minutes else None,
                'is_active': shift.is_active,
                'breaks': []
            }
            
            if employee:
                shift_info['employee_id'] = employee['id']
                shift_info['role'] = 'Worker'
            
            # Add break information
            for break_data in shift.breaks:
                shift_info['breaks'].append({
                    'start': break_data['start'].isoformat(),
                    'end': break_data['end'].isoformat() if break_data['end'] else None,
                    'duration_minutes': break_data['duration_minutes']
                })
            
            shift_data.append(shift_info)
        
        return jsonify({
            'success': True,
            'date': date,
            'shift_count': len(shift_data),
            'shifts': shift_data
        })
        
    except Exception as e:
        logger.error(f"Error getting shifts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@connecteam_bp.route('/employee/<int:employee_id>/shift-history', methods=['GET'])
@require_api_key
def get_employee_shift_history(employee_id):
    """Get shift history for an employee"""
    try:
        # Get date range from query params
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Validate dates
        if not validate_date(start_date) or not validate_date(end_date):
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }), 400
        
        # Get employee's Connecteam ID
        employee = get_sync_service().db.fetch_one(
            "SELECT name, connecteam_user_id FROM employees WHERE id = %s",
            (employee_id,)
        )
        
        if not employee or not employee['connecteam_user_id']:
            return jsonify({
                'success': False,
                'error': 'Employee not found or not linked to Connecteam'
            }), 404
        
        # Get shift history
        shifts = get_sync_service().client.get_shift_history(
            employee['connecteam_user_id'],
            start_date,
            end_date
        )
        
        shift_history = []
        total_minutes = 0
        
        for shift in shifts:
            shift_history.append({
                'date': shift.clock_in.strftime('%Y-%m-%d'),
                'clock_in': shift.clock_in.isoformat(),
                'clock_out': shift.clock_out.isoformat() if shift.clock_out else None,
                'total_minutes': round(shift.total_minutes, 1) if shift.total_minutes else None,
                'total_hours': round(shift.total_minutes / 60, 1) if shift.total_minutes else None
            })
            
            if shift.total_minutes and shift.clock_out:
                total_minutes += shift.total_minutes
        
        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'summary': {
                'total_shifts': len(shift_history),
                'total_minutes': round(total_minutes, 1),
                'total_hours': round(total_minutes / 60, 1),
                'average_shift_hours': round(total_minutes / 60 / len(shift_history), 1) if shift_history else 0
            },
            'shifts': shift_history
        })
        
    except Exception as e:
        logger.error(f"Error getting shift history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Add automatic sync endpoint
@connecteam_bp.route('/sync/auto', methods=['POST'])
@require_api_key
def toggle_auto_sync():
    """Enable/disable automatic synchronization"""
    try:
        enable = request.json.get('enable', True)
        
        # This would typically update a configuration or start/stop a scheduler
        # For now, just return status
        
        return jsonify({
            'success': True,
            'auto_sync_enabled': enable,
            'sync_interval': getattr(config, 'SYNC_INTERVAL', 300)
        })
        
    except Exception as e:
        logger.error(f"Error toggling auto sync: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
