"""Cache API endpoints for real-time data"""
from flask import Blueprint, jsonify, request
from datetime import datetime, date
import logging

from database.cache_manager import get_cache_manager
cache = get_cache_manager()
from database.db_manager import get_db
from calculations.activity_processor import ActivityProcessor

logger = logging.getLogger(__name__)

# Create blueprint
cache_bp = Blueprint('cache', __name__)

@cache_bp.route('/realtime/<int:employee_id>', methods=['GET'])
def get_employee_realtime(employee_id):
    """Get real-time statistics for an employee"""
    try:
        # Try cache first
        cached_data = cache.get_employee_realtime(employee_id)
        
        if cached_data:
            return jsonify({
                'source': 'cache',
                'data': cached_data
            })
        
        # If not in cache, calculate and cache
        processor = ActivityProcessor()
        stats = processor.get_real_time_stats(employee_id)
        
        if stats:
            # Cache for next time
            cache.set_employee_realtime(employee_id, stats)
            
            return jsonify({
                'source': 'calculated',
                'data': stats
            })
        else:
            return jsonify({'error': 'Employee not found'}), 404
            
    except Exception as e:
        logger.error(f"Error getting realtime stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cache_bp.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get current leaderboard"""
    try:
        # Get parameters
        date_str = request.args.get('date', date.today().isoformat())
        role_id = request.args.get('role_id', type=int)
        
        # Try cache first
        cached_data = cache.get_leaderboard(date_str, role_id)
        
        if cached_data:
            return jsonify({
                'source': 'cache',
                'data': cached_data
            })
        
        # If not in cache, query database
        db = get_db()
        
        where_clause = "WHERE ds.score_date = %s"
        params = [date_str]
        
        if role_id:
            where_clause += " AND e.role_id = %s"
            params.append(role_id)
        
        scores = db.execute_query(
            f"""
            SELECT 
                e.id,
                e.name,
                e.email,
                rc.role_name,
                ds.points_earned,
                ds.items_processed,
                ds.efficiency_rate
            FROM daily_scores ds
            JOIN employees e ON ds.employee_id = e.id
            JOIN role_configs rc ON e.role_id = rc.id
            {where_clause}
            ORDER BY ds.points_earned DESC
            LIMIT 50
            """,
            params
        )
        
        # Format scores
        formatted_scores = []
        for score in scores:
            formatted_scores.append({
                'employee_id': score['id'],
                'name': score['name'],
                'email': score['email'],
                'role': score['role_name'],
                'points_earned': float(score['points_earned']),
                'items_processed': score['items_processed'],
                'efficiency_rate': float(score['efficiency_rate'])
            })
        
        # Update cache
        cache.update_leaderboard(date_str, formatted_scores, role_id)
        
        # Get cached version (which includes ranks)
        cached_data = cache.get_leaderboard(date_str, role_id)
        
        return jsonify({
            'source': 'calculated',
            'data': cached_data
        })
        
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cache_bp.route('/team/stats', methods=['GET'])
def get_team_stats():
    """Get team statistics"""
    try:
        role_id = request.args.get('role_id', type=int)
        
        # Try cache first
        cached_data = cache.get_team_stats(role_id)
        
        if cached_data:
            return jsonify({
                'source': 'cache',
                'data': cached_data
            })
        
        # If not in cache, calculate
        processor = ActivityProcessor()
        stats = processor.get_team_real_time_stats(role_id)
        
        # Cache for next time
        cache.set_team_stats(stats, role_id)
        
        return jsonify({
            'source': 'calculated',
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting team stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cache_bp.route('/idle', methods=['GET'])
def get_idle_employees():
    """Get currently idle employees"""
    try:
        # Try cache first
        cached_data = cache.get_idle_employees()
        
        if cached_data:
            return jsonify({
                'source': 'cache',
                'data': cached_data
            })
        
        # If not in cache, return empty
        # (Idle detection runs on schedule and updates cache)
        return jsonify({
            'source': 'none',
            'data': {
                'timestamp': datetime.now().isoformat(),
                'count': 0,
                'employees': []
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting idle employees: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@cache_bp.route('/stats', methods=['GET'])
def get_cache_stats():
    """Get cache statistics"""
    try:
        stats = cache.get_cache_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500
