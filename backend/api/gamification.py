"""
API endpoints for gamification features
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, date
from calculations.gamification_engine import GamificationEngine
from api.auth import require_api_key
import logging

logger = logging.getLogger(__name__)

gamification_bp = Blueprint('gamification', __name__)

# Lazy-loaded engine
_engine = None

def get_engine():
    """Get engine instance (lazy initialization)"""
    global _engine
    if _engine is None:
        _engine = GamificationEngine()
    return _engine

@gamification_bp.route('/achievements/<int:employee_id>', methods=['GET'])
@require_api_key
def get_achievements(employee_id):
    """Get all achievements for an employee"""
    try:
        achievements = get_engine().get_employee_achievements(employee_id)
        return jsonify(achievements)
    except Exception as e:
        logger.error(f"Error getting achievements: {e}")
        return jsonify({'error': str(e)}), 500

@gamification_bp.route('/check-daily/<int:employee_id>', methods=['POST'])
@require_api_key
def check_daily_achievements(employee_id):
    """Check and award daily achievements"""
    try:
        data = request.get_json()
        check_date = data.get('date') if data else None
        
        if check_date:
            check_date = datetime.strptime(check_date, '%Y-%m-%d').date()
        else:
            check_date = date.today()
        
        earned = get_engine().check_daily_achievements(employee_id, check_date)
        
        return jsonify({
            'employee_id': employee_id,
            'date': check_date.isoformat(),
            'achievements_earned': len(earned),
            'achievements': [
                {
                    'name': a['name'],
                    'description': a['description'],
                    'points': a['points'],
                    'icon': a['icon']
                }
                for a in earned
            ]
        })
    except Exception as e:
        logger.error(f"Error checking daily achievements: {e}")
        return jsonify({'error': str(e)}), 500

@gamification_bp.route('/check-all/<int:employee_id>', methods=['POST'])
@require_api_key
def check_all_achievements(employee_id):
    """Check all achievement types for an employee"""
    try:
        daily = get_engine().check_daily_achievements(employee_id)
        streak = get_engine().check_streak_achievements(employee_id)
        milestone = get_engine().check_milestone_achievements(employee_id)
        
        all_earned = daily + streak + milestone
        
        return jsonify({
            'employee_id': employee_id,
            'total_earned': len(all_earned),
            'by_type': {
                'daily': len(daily),
                'streak': len(streak),
                'milestone': len(milestone)
            },
            'achievements': [
                {
                    'name': a['name'],
                    'description': a['description'],
                    'points': a['points'],
                    'icon': a['icon'],
                    'type': a['type'].value
                }
                for a in all_earned
            ]
        })
    except Exception as e:
        logger.error(f"Error checking all achievements: {e}")
        return jsonify({'error': str(e)}), 500

@gamification_bp.route('/leaderboard', methods=['GET'])
@require_api_key
def get_leaderboard():
    """Get gamification leaderboard"""
    try:
        period = request.args.get('period', 'weekly')
        
        if period not in ['daily', 'weekly', 'monthly', 'all']:
            return jsonify({'error': 'Invalid period. Use daily, weekly, monthly, or all'}), 400
        
        leaderboard = get_engine().get_leaderboard(period)
        
        return jsonify({
            'period': period,
            'generated_at': datetime.now().isoformat(),
            'leaderboard': leaderboard
        })
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'error': str(e)}), 500

@gamification_bp.route('/challenges', methods=['POST'])
@require_api_key
def create_challenge():
    """Create a new team challenge"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required = ['challenge_type', 'target_value', 'start_date', 'end_date']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        challenge_id = get_engine().create_team_challenge(
            role_id=data.get('role_id'),
            challenge_type=data['challenge_type'],
            target_value=float(data['target_value']),
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        )
        
        return jsonify({
            'success': True,
            'challenge_id': challenge_id,
            'message': 'Challenge created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating challenge: {e}")
        return jsonify({'error': str(e)}), 500

@gamification_bp.route('/challenges/active', methods=['GET'])
@require_api_key
def get_active_challenges():
    """Get all active challenges"""
    try:
        from database.db_manager import DatabaseManager
        
        db_manager = DatabaseManager()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    tc.*,
                    rc.role_name,
                    COUNT(DISTINCT cp.employee_id) as participant_count,
                    DATEDIFF(tc.end_date, CURDATE()) as days_remaining
                FROM team_challenges tc
                LEFT JOIN role_configs rc ON tc.role_id = rc.id
                LEFT JOIN challenge_participants cp ON tc.id = cp.challenge_id
                WHERE tc.is_active = TRUE
                AND tc.end_date >= CURDATE()
                GROUP BY tc.id
                ORDER BY tc.end_date
            """)
            
            challenges = []
            for row in cursor.fetchall():
                progress_percent = (float(row['current_value']) / float(row['target_value']) * 100) if row['target_value'] > 0 else 0
                
                challenges.append({
                    'id': row['id'],
                    'role': row['role_name'] or 'All Roles',
                    'type': row['challenge_type'],
                    'name': row['challenge_name'],
                    'description': row['description'],
                    'target': float(row['target_value']),
                    'current': float(row['current_value']),
                    'progress_percent': round(progress_percent, 1),
                    'participants': row['participant_count'],
                    'days_remaining': row['days_remaining'],
                    'reward_points': row['reward_points'],
                    'start_date': row['start_date'].isoformat(),
                    'end_date': row['end_date'].isoformat()
                })
            
            return jsonify({
                'active_challenges': len(challenges),
                'challenges': challenges
            })
            
    except Exception as e:
        logger.error(f"Error getting active challenges: {e}")
        return jsonify({'error': str(e)}), 500
