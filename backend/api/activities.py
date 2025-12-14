"""Activity API endpoints for PodFactory integration"""
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List
import logging

from database.db_manager import get_db
from database.queries import (
    GET_EMPLOYEE_BY_EMAIL, 
    INSERT_ACTIVITY,
    GET_ROLE_BY_NAME
)
from models import ActivityLog
from api.validators import validate_activity_data, validate_batch_activities
from calculations.activity_flagger import ActivityFlagger
from api.auth import require_api_key, rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
activity_bp = Blueprint('activities', __name__)

@activity_bp.route('/activity', methods=['POST'])
@require_api_key
@rate_limit(requests_per_minute=100)
def create_activity():
    """
    Create a single activity record from PodFactory
    
    Expected JSON:
    {
        "report_id": "ACT-20241115-1030-JD-PICK",
        "user_email": "john.doe@company.com",
        "user_name": "John Doe",
        "user_role": "Picker",
        "items_count": 25,
        "window_start": "2024-11-15 10:30:00",
        "window_end": "2024-11-15 10:39:59"
    }
    """
    try:
        # Get JSON data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate data
        validation_error = validate_activity_data(data)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Get database instance
        db = get_db()
        
        # Check if employee exists
        employee = db.execute_one(GET_EMPLOYEE_BY_EMAIL, (data['user_email'],))
        if not employee:
            return jsonify({
                'error': f"Employee not found: {data['user_email']}",
                'details': 'Employee must be registered in the system first'
            }), 404
        
        # Get role configuration
        role = db.execute_one(GET_ROLE_BY_NAME, (data['user_role'],))
        if not role:
            return jsonify({
                'error': f"Invalid role: {data['user_role']}",
                'valid_roles': ['Heat Pressing', 'Packing and Shipping', 'Picker', 'Labeler', 'Film Matching']
            }), 400
        
        # Verify employee has correct role
        if employee['role_id'] != role['id']:
            return jsonify({
                'error': 'Role mismatch',
                'details': f"Employee {employee['name']} is registered as {employee['role_name']}, not {data['user_role']}"
            }), 400
        
        # Parse timestamps
        window_start = datetime.strptime(data['window_start'], '%Y-%m-%d %H:%M:%S')
        window_end = datetime.strptime(data['window_end'], '%Y-%m-%d %H:%M:%S')
        
        # Check for duplicate
        existing = db.execute_one(
            "SELECT id FROM activity_logs WHERE report_id = %s",
            (data['report_id'],)
        )
        if existing:
            return jsonify({
                'error': 'Duplicate activity',
                'report_id': data['report_id'],
                'existing_id': existing['id']
            }), 409
        
        # Insert activity
        activity_id = db.execute_update(
            INSERT_ACTIVITY,
            (
                data['report_id'],
                employee['id'],
                role['id'],
                data['items_count'],
                window_start,
                window_end
            )
        )
        
        # Check for flags
        flagger = ActivityFlagger()
        activity_data = {
            'id': activity_id,
            'employee_id': employee['id'],
            'role_id': role['id'],
            'items_count': data['items_count'],
            'window_start': window_start,
            'window_end': window_end
        }
        
        flags = flagger.check_activity(activity_data)
        if flags:
            flagger.create_flags(activity_id, flags)
            logger.warning(f"Activity {activity_id} flagged: {len(flags)} flags")
        
        # Log successful insertion
        logger.info(f"Activity created: {data['report_id']} for {employee['name']}")
        
        return jsonify({
            'success': True,
            'activity_id': activity_id,
            'report_id': data['report_id'],
            'employee': employee['name'],
            'items': data['items_count']
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating activity: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@activity_bp.route('/activity/batch', methods=['POST'])
@require_api_key
@rate_limit(requests_per_minute=20)
def create_batch_activities():
    """
    Create multiple activity records at once
    
    Expected JSON:
    {
        "activities": [
            {
                "report_id": "ACT-20241115-1030-JD-PICK",
                "user_email": "john.doe@company.com",
                "user_name": "John Doe",
                "user_role": "Picker",
                "items_count": 25,
                "window_start": "2024-11-15 10:30:00",
                "window_end": "2024-11-15 10:39:59"
            },
            ...
        ]
    }
    """
    try:
        # Get JSON data
        data = request.get_json()
        if not data or 'activities' not in data:
            return jsonify({'error': 'No activities provided'}), 400
        
        activities = data['activities']
        if not isinstance(activities, list):
            return jsonify({'error': 'Activities must be a list'}), 400
        
        if len(activities) == 0:
            return jsonify({'error': 'Empty activities list'}), 400
        
        if len(activities) > 1000:
            return jsonify({'error': 'Too many activities. Maximum 1000 per batch'}), 400
        
        # Validate all activities
        validation_errors = validate_batch_activities(activities)
        if validation_errors:
            return jsonify({
                'error': 'Validation errors',
                'details': validation_errors
            }), 400
        
        # Process activities with batch lookups (N+1 query fix)
        db = get_db()
        success_count = 0
        errors = []
        processed = []

        # Batch fetch: employees by email (1 query instead of N)
        unique_emails = list(set(a['user_email'] for a in activities))
        if unique_emails:
            placeholders = ','.join(['%s'] * len(unique_emails))
            employees_list = db.execute_query(
                f"SELECT id, email, name, role_id FROM employees WHERE email IN ({placeholders})",
                tuple(unique_emails)
            )
            employee_map = {e['email']: e for e in employees_list}
        else:
            employee_map = {}

        # Batch fetch: roles by name (1 query instead of N)
        unique_roles = list(set(a['user_role'] for a in activities))
        if unique_roles:
            placeholders = ','.join(['%s'] * len(unique_roles))
            roles_list = db.execute_query(
                f"SELECT id, role_name FROM role_configs WHERE role_name IN ({placeholders})",
                tuple(unique_roles)
            )
            role_map = {r['role_name']: r for r in roles_list}
        else:
            role_map = {}

        # Batch check duplicates (1 query instead of N)
        report_ids = [a['report_id'] for a in activities]
        if report_ids:
            placeholders = ','.join(['%s'] * len(report_ids))
            existing_list = db.execute_query(
                f"SELECT report_id FROM activity_logs WHERE report_id IN ({placeholders})",
                tuple(report_ids)
            )
            existing_ids = {e['report_id'] for e in existing_list}
        else:
            existing_ids = set()

        # Process with O(1) lookups
        for idx, activity_data in enumerate(activities):
            try:
                # Check employee (O(1) dict lookup)
                employee = employee_map.get(activity_data['user_email'])
                if not employee:
                    errors.append({
                        'index': idx,
                        'report_id': activity_data['report_id'],
                        'error': f"Employee not found: {activity_data['user_email']}"
                    })
                    continue

                # Check role (O(1) dict lookup)
                role = role_map.get(activity_data['user_role'])
                if not role or employee['role_id'] != role['id']:
                    errors.append({
                        'index': idx,
                        'report_id': activity_data['report_id'],
                        'error': 'Invalid or mismatched role'
                    })
                    continue

                # Check duplicate (O(1) set lookup)
                if activity_data['report_id'] in existing_ids:
                    errors.append({
                        'index': idx,
                        'report_id': activity_data['report_id'],
                        'error': 'Duplicate activity'
                    })
                    continue

                # Parse timestamps
                window_start = datetime.strptime(activity_data['window_start'], '%Y-%m-%d %H:%M:%S')
                window_end = datetime.strptime(activity_data['window_end'], '%Y-%m-%d %H:%M:%S')

                # Insert activity
                activity_id = db.execute_update(
                    INSERT_ACTIVITY,
                    (
                        activity_data['report_id'],
                        employee['id'],
                        role['id'],
                        activity_data['items_count'],
                        window_start,
                        window_end
                    )
                )

                # Track for duplicate prevention within same batch
                existing_ids.add(activity_data['report_id'])

                success_count += 1
                processed.append({
                    'report_id': activity_data['report_id'],
                    'activity_id': activity_id
                })

            except Exception as e:
                errors.append({
                    'index': idx,
                    'report_id': activity_data.get('report_id', 'unknown'),
                    'error': str(e)
                })
        
        # Return results
        return jsonify({
            'success': success_count > 0,
            'total': len(activities),
            'processed': success_count,
            'failed': len(errors),
            'errors': errors[:10] if errors else [],  # Limit error details
            'processed_ids': processed[:100]  # Limit processed details
        }), 201 if success_count > 0 else 400
        
    except Exception as e:
        logger.error(f"Error in batch activity creation: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@activity_bp.route('/activity/<date>', methods=['GET'])
def get_activities_by_date(date):
    """Get all activities for a specific date"""
    try:
        # Validate date format
        try:
            query_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Get activities
        db = get_db()
        activities = db.execute_query(
            """
            SELECT a.*, e.name as employee_name, rc.role_name
            FROM activity_logs a
            JOIN employees e ON a.employee_id = e.id
            JOIN role_configs rc ON a.role_id = rc.id
            WHERE DATE(a.window_start) = %s
            ORDER BY a.window_start, e.name
            """,
            (query_date,)
        )
        
        # Format response
        return jsonify({
            'date': date,
            'total_activities': len(activities),
            'activities': [
                {
                    'id': a['id'],
                    'report_id': a['report_id'],
                    'employee_name': a['employee_name'],
                    'role_name': a['role_name'],
                    'items_count': a['items_count'],
                    'window_start': a['window_start'].isoformat(),
                    'window_end': a['window_end'].isoformat()
                }
                for a in activities
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting activities: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
