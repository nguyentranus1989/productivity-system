"""Flag management API endpoints"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

from database.db_manager import get_db
from calculations.activity_flagger import ActivityFlagger
from api.auth import require_api_key, rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
flags_bp = Blueprint('flags', __name__)

@flags_bp.route('/unreviewed', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=60)
def get_unreviewed_flags():
    """Get list of unreviewed activity flags"""
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Cap at 100
        
        flagger = ActivityFlagger()
        flags = flagger.get_unreviewed_flags(limit)
        
        # Group by flag type
        by_type = {}
        for flag in flags:
            flag_type = flag['flag_type']
            if flag_type not in by_type:
                by_type[flag_type] = []
            by_type[flag_type].append({
                'id': flag['id'],
                'activity_id': flag['activity_log_id'],
                'report_id': flag['report_id'],
                'employee_name': flag['employee_name'],
                'role': flag['role_name'],
                'items_count': flag['items_count'],
                'window_start': flag['window_start'].isoformat(),
                'reason': flag['flag_reason'],
                'created_at': flag['created_at'].isoformat()
            })
        
        return jsonify({
            'total': len(flags),
            'by_type': by_type,
            'types': list(by_type.keys())
        })
        
    except Exception as e:
        logger.error(f"Error getting unreviewed flags: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@flags_bp.route('/<int:flag_id>/review', methods=['POST'])
@require_api_key
@rate_limit(requests_per_minute=100)
def review_flag(flag_id):
    """Mark a flag as reviewed"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        reviewer_id = data.get('reviewer_id')
        if not reviewer_id:
            return jsonify({'error': 'reviewer_id required'}), 400
        
        review_notes = data.get('notes', '')
        
        flagger = ActivityFlagger()
        success = flagger.review_flag(flag_id, reviewer_id, review_notes)
        
        if success:
            logger.info(f"Flag {flag_id} reviewed by employee {reviewer_id}")
            return jsonify({
                'success': True,
                'flag_id': flag_id,
                'reviewed_at': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Failed to review flag'}), 500
            
    except Exception as e:
        logger.error(f"Error reviewing flag: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@flags_bp.route('/stats', methods=['GET'])
@require_api_key
@rate_limit(requests_per_minute=60)
def get_flag_stats():
    """Get flag statistics"""
    try:
        db = get_db()
        
        # Get overall stats
        overall = db.execute_one(
            """
            SELECT 
                COUNT(*) as total_flags,
                SUM(CASE WHEN is_reviewed = TRUE THEN 1 ELSE 0 END) as reviewed,
                SUM(CASE WHEN is_reviewed = FALSE THEN 1 ELSE 0 END) as unreviewed
            FROM activity_flags
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """
        )
        
        # Get stats by type
        by_type = db.execute_query(
            """
            SELECT 
                flag_type,
                COUNT(*) as count,
                SUM(CASE WHEN is_reviewed = FALSE THEN 1 ELSE 0 END) as unreviewed
            FROM activity_flags
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY flag_type
            ORDER BY count DESC
            """
        )
        
        # Get top flagged employees
        top_employees = db.execute_query(
            """
            SELECT 
                e.name,
                e.email,
                rc.role_name,
                COUNT(af.id) as flag_count
            FROM activity_flags af
            JOIN activity_logs a ON af.activity_log_id = a.id
            JOIN employees e ON a.employee_id = e.id
            JOIN role_configs rc ON e.role_id = rc.id
            WHERE af.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY e.id, e.name, e.email, rc.role_name
            ORDER BY flag_count DESC
            LIMIT 10
            """
        )
        
        return jsonify({
            'period': 'last_30_days',
            'overall': {
                'total': overall['total_flags'],
                'reviewed': overall['reviewed'],
                'unreviewed': overall['unreviewed'],
                'review_rate': (overall['reviewed'] / overall['total_flags'] * 100) 
                              if overall['total_flags'] > 0 else 0
            },
            'by_type': [
                {
                    'type': t['flag_type'],
                    'total': t['count'],
                    'unreviewed': t['unreviewed']
                }
                for t in by_type
            ],
            'top_flagged_employees': [
                {
                    'name': e['name'],
                    'email': e['email'],
                    'role': e['role_name'],
                    'flags': e['flag_count']
                }
                for e in top_employees
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting flag stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500
