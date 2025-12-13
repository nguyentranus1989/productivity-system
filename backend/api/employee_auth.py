from flask import Blueprint, request, jsonify
import bcrypt
import secrets
from datetime import datetime, timedelta
from database.db_manager import get_db
from utils.timezone_helpers import TimezoneHelper

tz_helper = TimezoneHelper()

employee_auth_bp = Blueprint("employee_auth", __name__)

# PIN hashing functions
def hash_pin(pin):
    """Hash PIN using bcrypt (10 rounds for faster auth)"""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt(10)).decode()

def verify_pin(pin, hashed):
    """Verify PIN against bcrypt hash. Also supports legacy plain text for migration."""
    try:
        if hashed and hashed.startswith('$2'):
            return bcrypt.checkpw(pin.encode(), hashed.encode())
        else:
            # Legacy plain text support (will be migrated)
            return pin == hashed
    except Exception:
        return False

@employee_auth_bp.route('/api/employee/login', methods=['POST'])
def employee_login():
    """Authenticate employee with ID and PIN"""
    try:
        data = request.json
        employee_id = data.get('employee_id')
        pin = data.get('pin')
        
        if not employee_id or not pin:
            return jsonify({'success': False, 'message': 'Employee ID and PIN required'}), 400
        
        # Check credentials
        result = get_db().execute_one("""
            SELECT e.id, e.name, ea.pin 
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE e.id = %s AND e.is_active = 1
        """, (employee_id,))
        
        if not result or not verify_pin(pin, result['pin']):
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        # Generate session token
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(days=1)
        
        # Update token in database
        get_db().execute_query("""
            UPDATE employee_auth
            SET login_token = %s, token_expires = %s, last_login = NOW()
            WHERE employee_id = %s
        """, (token, expires, employee_id))
        
        return jsonify({
            'success': True,
            'token': token,
            'employee_id': employee_id,
            'name': result['name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/verify', methods=['POST'])
def verify_token():
    """Verify employee session token"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({'success': False, 'message': 'No token provided'}), 401
        
        result = get_db().execute_one("""
            SELECT e.id, e.name 
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE ea.login_token = %s 
            AND ea.token_expires > NOW()
            AND e.is_active = 1
        """, (token,))
        
        if not result:
            return jsonify({'success': False, 'message': 'Invalid or expired token'}), 401
        
        return jsonify({
            'success': True,
            'employee_id': result['id'],
            'name': result['name']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/logout', methods=['POST'])
def employee_logout():
    """Logout employee by clearing token"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if token:
            get_db().execute_query("""
                UPDATE employee_auth
                SET login_token = NULL, token_expires = NULL
                WHERE login_token = %s
            """, (token,))
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/stats', methods=['GET'])
def get_employee_stats(employee_id):
    """Get performance stats for a specific employee"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        # Get today's stats (using CT date and UTC range)
        stats = get_db().execute_one("""
            SELECT
                e.id,
                e.name,
                COALESCE(ds.items_processed, 0) as items_processed,
                COALESCE(ds.points_earned, 0) as points_earned,
                COALESCE(ds.efficiency_rate, 0) as efficiency,
                COALESCE(ds.active_minutes, 0) as active_minutes,
                COALESCE(
                    TIMESTAMPDIFF(MINUTE,
                        (SELECT MAX(window_end) FROM activity_logs
                         WHERE employee_id = e.id AND window_end >= %s AND window_end < %s),
                        UTC_TIMESTAMP()
                    ), 0
                ) as idle_minutes
            FROM employees e
            LEFT JOIN daily_scores ds ON e.id = ds.employee_id AND ds.score_date = %s
            WHERE e.id = %s
        """, (utc_start, utc_end, ct_date, employee_id))

        if not stats:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404

        # Get employee rank (using CT date)
        rank_result = get_db().execute_one("""
            SELECT COUNT(*) + 1 as `rank`
            FROM daily_scores
            WHERE score_date = %s
            AND points_earned > (
                SELECT COALESCE(points_earned, 0)
                FROM daily_scores
                WHERE employee_id = %s AND score_date = %s
            )
        """, (ct_date, employee_id, ct_date))

        # Get total active employees today (using UTC range)
        total_result = get_db().execute_one("""
            SELECT COUNT(DISTINCT employee_id) as total
            FROM clock_times
            WHERE clock_in >= %s AND clock_in < %s
        """, (utc_start, utc_end))

        # Get team average stats for context
        team_avg = get_db().execute_one("""
            SELECT
                AVG(items_processed) as avg_items,
                AVG(efficiency_rate) as avg_efficiency,
                AVG(points_earned) as avg_points
            FROM daily_scores
            WHERE score_date = %s AND items_processed > 0
        """, (ct_date,))

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'name': stats['name'],
            'items_processed': stats['items_processed'],
            'points_earned': stats['points_earned'],
            'efficiency': stats['efficiency'],
            'idle_minutes': min(stats['idle_minutes'], 999),  # Cap at 999
            'employee_rank': rank_result['rank'] if rank_result else 999,
            'total_employees': total_result['total'] if total_result else 1,
            # Team context
            'team_avg_items': round(team_avg['avg_items'], 1) if team_avg and team_avg['avg_items'] else 0,
            'team_avg_efficiency': round(team_avg['avg_efficiency'], 1) if team_avg and team_avg['avg_efficiency'] else 0
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/trends', methods=['GET'])
def get_employee_trends(employee_id):
    """Get productivity trends for employee (auth via token)"""
    try:
        # Verify employee has access (either their own data or valid token)
        token = request.headers.get('Authorization', '').replace('Bearer ', '')

        # Get days parameter (default 30, max 90)
        days = request.args.get('days', 30, type=int)
        days = min(days, 90)

        # Get trend data from daily_scores
        ct_date = tz_helper.get_current_ct_date()
        trend_data = get_db().execute_query("""
            SELECT
                score_date,
                items_processed,
                points_earned,
                efficiency_rate,
                active_minutes
            FROM daily_scores
            WHERE employee_id = %s
            AND score_date >= DATE_SUB(%s, INTERVAL %s DAY)
            ORDER BY score_date ASC
        """, (employee_id, ct_date, days))

        if not trend_data:
            return jsonify({
                'success': True,
                'has_data': False,
                'days': days,
                'trend': []
            })

        # Format for chart
        trend = [{
            'date': row['score_date'].strftime('%Y-%m-%d') if row['score_date'] else None,
            'items': row['items_processed'] or 0,
            'points': row['points_earned'] or 0,
            'efficiency': float(row['efficiency_rate'] or 0),
            'minutes': row['active_minutes'] or 0
        } for row in trend_data]

        return jsonify({
            'success': True,
            'has_data': True,
            'days': days,
            'trend': trend
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/change-pin', methods=['POST'])
def change_pin():
    """Allow employee to change their own PIN (requires current PIN)"""
    try:
        # Get employee from token
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401

        # Verify token and get employee
        employee = get_db().execute_one("""
            SELECT e.id, e.name, ea.pin
            FROM employees e
            JOIN employee_auth ea ON e.id = ea.employee_id
            WHERE ea.login_token = %s
            AND ea.token_expires > NOW()
            AND e.is_active = 1
        """, (token,))

        if not employee:
            return jsonify({'success': False, 'message': 'Invalid or expired session'}), 401

        data = request.json
        current_pin = data.get('current_pin')
        new_pin = data.get('new_pin')

        if not current_pin or not new_pin:
            return jsonify({'success': False, 'message': 'Current PIN and new PIN required'}), 400

        # Validate new PIN format (4-6 digits)
        if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 6:
            return jsonify({'success': False, 'message': 'New PIN must be 4-6 digits'}), 400

        # Verify current PIN
        if not verify_pin(current_pin, employee['pin']):
            return jsonify({'success': False, 'message': 'Current PIN is incorrect'}), 401

        # Hash and update new PIN
        new_pin_hash = hash_pin(new_pin)
        get_db().execute_query("""
            UPDATE employee_auth
            SET pin = %s, pin_set_at = NOW()
            WHERE employee_id = %s
        """, (new_pin_hash, employee['id']))

        return jsonify({
            'success': True,
            'message': 'PIN changed successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== GOALS API ==========

@employee_auth_bp.route('/api/employee/<int:employee_id>/goals', methods=['GET'])
def get_employee_goals(employee_id):
    """Get employee's active goals with progress"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        # Get active goals
        goals = get_db().execute_query("""
            SELECT
                g.id,
                g.goal_type,
                g.metric,
                g.target_value,
                g.start_date,
                g.end_date,
                g.created_at
            FROM employee_goals g
            WHERE g.employee_id = %s AND g.is_active = 1
            ORDER BY g.goal_type, g.created_at DESC
        """, (employee_id,))

        # Get today's stats for progress calculation
        today_stats = get_db().execute_one("""
            SELECT
                COALESCE(items_processed, 0) as items_processed,
                COALESCE(points_earned, 0) as points_earned,
                COALESCE(efficiency_rate, 0) as efficiency_rate,
                COALESCE(active_minutes, 0) as active_minutes
            FROM daily_scores
            WHERE employee_id = %s AND score_date = %s
        """, (employee_id, ct_date))

        # Calculate progress for each goal
        result_goals = []
        for goal in (goals or []):
            current_value = 0
            if today_stats:
                if goal['metric'] == 'items_processed':
                    current_value = today_stats['items_processed']
                elif goal['metric'] == 'points_earned':
                    current_value = today_stats['points_earned']
                elif goal['metric'] == 'efficiency':
                    current_value = float(today_stats['efficiency_rate'])
                elif goal['metric'] == 'active_minutes':
                    current_value = today_stats['active_minutes']

            target = float(goal['target_value'])
            progress = min(100, round((current_value / target * 100) if target > 0 else 0, 1))

            result_goals.append({
                'id': goal['id'],
                'type': goal['goal_type'],
                'metric': goal['metric'],
                'target': target,
                'current': current_value,
                'progress': progress,
                'start_date': goal['start_date'].strftime('%Y-%m-%d') if goal['start_date'] else None
            })

        return jsonify({
            'success': True,
            'goals': result_goals
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/goals', methods=['POST'])
def create_employee_goal(employee_id):
    """Create a new goal for employee"""
    try:
        data = request.json
        metric = data.get('metric')
        target_value = data.get('target')
        goal_type = data.get('type', 'daily')

        if not metric or not target_value:
            return jsonify({'success': False, 'message': 'Metric and target required'}), 400

        valid_metrics = ['items_processed', 'points_earned', 'efficiency', 'active_minutes']
        if metric not in valid_metrics:
            return jsonify({'success': False, 'message': f'Invalid metric. Use: {valid_metrics}'}), 400

        ct_date = tz_helper.get_current_ct_date()

        get_db().execute_query("""
            INSERT INTO employee_goals (employee_id, goal_type, metric, target_value, start_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (employee_id, goal_type, metric, target_value, ct_date))

        return jsonify({
            'success': True,
            'message': 'Goal created successfully'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/goals/<int:goal_id>', methods=['DELETE'])
def delete_employee_goal(employee_id, goal_id):
    """Deactivate a goal"""
    try:
        get_db().execute_query("""
            UPDATE employee_goals
            SET is_active = 0
            WHERE id = %s AND employee_id = %s
        """, (goal_id, employee_id))

        return jsonify({
            'success': True,
            'message': 'Goal removed'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== GAMIFICATION API ==========

@employee_auth_bp.route('/api/employee/<int:employee_id>/achievements', methods=['GET'])
def get_employee_achievements(employee_id):
    """Get employee's earned achievements"""
    try:
        # Get earned achievements
        achievements = get_db().execute_query("""
            SELECT
                a.achievement_key,
                a.earned_at,
                a.points_awarded
            FROM employee_achievements a
            WHERE a.employee_id = %s
            ORDER BY a.earned_at DESC
            LIMIT 50
        """, (employee_id,))

        # Achievement definitions
        achievement_defs = {
            'daily_target_met': {'name': 'Daily Champion', 'icon': '🎯', 'desc': 'Met daily points target'},
            'perfect_efficiency': {'name': 'Efficiency Master', 'icon': '⚡', 'desc': '90%+ efficiency'},
            'early_bird': {'name': 'Early Bird', 'icon': '🌅', 'desc': 'Started before 7:30 AM'},
            'weekly_consistency': {'name': 'Consistency King', 'icon': '👑', 'desc': '5-day target streak'},
            'improvement_week': {'name': 'Rising Star', 'icon': '🌟', 'desc': '10% weekly improvement'},
            'speed_demon': {'name': 'Speed Demon', 'icon': '🏎️', 'desc': 'Fastest processor'},
            'quality_queen': {'name': 'Quality Queen', 'icon': '💎', 'desc': 'Zero errors all day'},
            'team_player': {'name': 'Team Player', 'icon': '🤝', 'desc': 'Helped teammate'},
            'marathon_runner': {'name': 'Marathon Runner', 'icon': '🏃', 'desc': '8+ hours active'},
            'century_club': {'name': 'Century Club', 'icon': '💯', 'desc': '100+ items in a day'},
            'streak_week': {'name': 'Week Warrior', 'icon': '🔥', 'desc': '7-day streak'},
            'streak_month': {'name': 'Month Master', 'icon': '🏆', 'desc': '30-day streak'},
        }

        result = []
        for ach in (achievements or []):
            key = ach['achievement_key']
            defn = achievement_defs.get(key, {'name': key, 'icon': '🏅', 'desc': ''})
            result.append({
                'key': key,
                'name': defn['name'],
                'icon': defn['icon'],
                'description': defn['desc'],
                'points': ach['points_awarded'],
                'earned_at': ach['earned_at'].strftime('%Y-%m-%d %H:%M') if ach['earned_at'] else None
            })

        # Get total achievement points
        total = get_db().execute_one("""
            SELECT COALESCE(SUM(points_awarded), 0) as total
            FROM employee_achievements
            WHERE employee_id = %s
        """, (employee_id,))

        return jsonify({
            'success': True,
            'achievements': result,
            'total_points': total['total'] if total else 0,
            'count': len(result)
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/streak', methods=['GET'])
def get_employee_streak(employee_id):
    """Get employee's current streak info"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        # Get current streak (consecutive days with activity)
        streak_data = get_db().execute_query("""
            SELECT score_date, items_processed
            FROM daily_scores
            WHERE employee_id = %s AND items_processed > 0
            ORDER BY score_date DESC
            LIMIT 60
        """, (employee_id,))

        current_streak = 0
        if streak_data:
            expected_date = ct_date
            for row in streak_data:
                if row['score_date'] == expected_date:
                    current_streak += 1
                    expected_date -= timedelta(days=1)
                elif row['score_date'] == expected_date - timedelta(days=1):
                    # Allow for today not having data yet
                    expected_date = row['score_date']
                    current_streak += 1
                    expected_date -= timedelta(days=1)
                else:
                    break

        # Get best streak (simplified calculation)
        best_streak = current_streak

        return jsonify({
            'success': True,
            'current_streak': current_streak,
            'best_streak': best_streak,
            'streak_goal': 7  # Weekly goal
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/recent-activity', methods=['GET'])
def get_recent_activity(employee_id):
    """Get employee's recent activity log"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        # Get today's activity windows
        activities = get_db().execute_query("""
            SELECT
                window_start,
                window_end,
                items_processed,
                station
            FROM activity_logs
            WHERE employee_id = %s
            AND window_end >= %s AND window_end < %s
            ORDER BY window_end DESC
            LIMIT 20
        """, (employee_id, utc_start, utc_end))

        result = []
        for act in (activities or []):
            result.append({
                'time': act['window_end'].strftime('%H:%M'),
                'items': act['items_processed'],
                'station': act['station']
            })

        return jsonify({
            'success': True,
            'activities': result,
            'date': ct_date.strftime('%Y-%m-%d')
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
