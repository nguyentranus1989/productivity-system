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

        # Get hours clocked in today
        clock_time = get_db().execute_one("""
            SELECT
                MIN(clock_in) as first_clock_in,
                MAX(clock_out) as last_clock_out
            FROM clock_times
            WHERE employee_id = %s AND clock_in >= %s AND clock_in < %s
        """, (employee_id, utc_start, utc_end))

        hours_today = 0
        if clock_time and clock_time['first_clock_in']:
            from datetime import datetime
            clock_in = clock_time['first_clock_in']
            clock_out = clock_time['last_clock_out'] or datetime.utcnow()
            hours_today = round((clock_out - clock_in).total_seconds() / 3600, 1)

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'name': stats['name'],
            'items_processed': stats['items_processed'],
            'points_earned': stats['points_earned'],
            'efficiency': stats['efficiency'],
            'active_minutes': stats['active_minutes'],
            'hours_today': hours_today,
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
                items_count,
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
                'items': act['items_count'],
                'station': act['station']
            })

        return jsonify({
            'success': True,
            'activities': result,
            'date': ct_date.strftime('%Y-%m-%d')
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== SCHEDULE API ==========

@employee_auth_bp.route('/api/employee/<int:employee_id>/schedule', methods=['GET'])
def get_employee_schedule(employee_id):
    """Get employee's schedule for current/upcoming weeks from published_shifts"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        db = get_db()

        # Get current week start (Sunday for display)
        days_since_sunday = (ct_date.weekday() + 1) % 7
        current_week_start = ct_date - timedelta(days=days_since_sunday)
        next_week_start = current_week_start + timedelta(days=7)
        two_weeks_end = next_week_start + timedelta(days=7)

        # Get approved time-off dates for this employee
        time_off_dates = set()
        time_off = db.execute_query("""
            SELECT start_date, end_date, notes
            FROM time_off
            WHERE employee_id = %s
            AND is_approved = 1
            AND end_date >= %s
            AND start_date < %s
        """, (employee_id, current_week_start, two_weeks_end))

        import json
        for to in (time_off or []):
            # Check if notes contains specific dates
            specific_dates = None
            if to.get('notes'):
                try:
                    notes_data = json.loads(to['notes'])
                    if isinstance(notes_data, dict) and 'dates' in notes_data:
                        specific_dates = notes_data['dates']
                except (json.JSONDecodeError, TypeError):
                    pass

            if specific_dates:
                # Use specific dates from notes
                for date_str in specific_dates:
                    time_off_dates.add(date_str)
            else:
                # Fall back to full range
                current = to['start_date']
                while current <= to['end_date']:
                    time_off_dates.add(current.strftime('%Y-%m-%d'))
                    current += timedelta(days=1)

        # Get shifts from published_shifts (use DISTINCT to avoid duplicates, take latest schedule)
        shifts = db.execute_query("""
            SELECT DISTINCT
                ps.shift_date,
                ps.start_time,
                ps.end_time,
                ps.station,
                pub.status as schedule_status
            FROM published_shifts ps
            JOIN published_schedules pub ON ps.schedule_id = pub.id
            WHERE ps.employee_id = %s
            AND ps.shift_date >= %s
            AND ps.shift_date < %s
            AND ps.schedule_id = (
                SELECT MAX(id) FROM published_schedules
                WHERE week_start_date = pub.week_start_date
            )
            ORDER BY ps.shift_date
        """, (employee_id, current_week_start, two_weeks_end))

        # Group shifts by week, excluding time-off dates
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        weeks = {}

        for shift in (shifts or []):
            shift_date = shift['shift_date']
            date_str = shift_date.strftime('%Y-%m-%d')

            # Skip if this date is approved time-off
            if date_str in time_off_dates:
                continue

            # Find week start (Sunday) for this shift
            days_from_sunday = (shift_date.weekday() + 1) % 7
            week_start = shift_date - timedelta(days=days_from_sunday)
            week_key = week_start.strftime('%Y-%m-%d')

            if week_key not in weeks:
                weeks[week_key] = {
                    'week_start': week_key,
                    'status': shift['schedule_status'] or 'draft',
                    'days': {}
                }

            day_name = day_names[(shift_date.weekday() + 1) % 7]
            weeks[week_key]['days'][date_str] = {
                'day': day_name,
                'date': date_str,
                'start': str(shift['start_time'])[:5] if shift['start_time'] else None,
                'end': str(shift['end_time'])[:5] if shift['end_time'] else None,
                'station': shift['station'] or ''
            }

        # Convert to list format with all 7 days per week
        result = []
        for week_key in sorted(weeks.keys()):
            week_data = weeks[week_key]
            week_start_date = datetime.strptime(week_key, '%Y-%m-%d').date()

            days_list = []
            for i in range(7):
                day_date = week_start_date + timedelta(days=i)
                date_str = day_date.strftime('%Y-%m-%d')

                if date_str in week_data['days']:
                    days_list.append(week_data['days'][date_str])
                elif date_str in time_off_dates:
                    # Show as time-off day
                    days_list.append({
                        'day': day_names[i],
                        'date': date_str,
                        'off': True,
                        'time_off': True
                    })
                else:
                    days_list.append({
                        'day': day_names[i],
                        'date': date_str,
                        'off': True
                    })

            result.append({
                'week_start': week_key,
                'status': week_data['status'],
                'days': days_list
            })

        # If no schedules found, still return current and next week structure
        if not result:
            for week_start in [current_week_start, next_week_start]:
                week_key = week_start.strftime('%Y-%m-%d')
                days_list = []
                for i in range(7):
                    day_date = week_start + timedelta(days=i)
                    date_str = day_date.strftime('%Y-%m-%d')
                    if date_str in time_off_dates:
                        days_list.append({
                            'day': day_names[i],
                            'date': date_str,
                            'off': True,
                            'time_off': True
                        })
                    else:
                        days_list.append({
                            'day': day_names[i],
                            'date': date_str,
                            'off': True
                        })
                result.append({
                    'week_start': week_key,
                    'status': 'none',
                    'days': days_list
                })

        return jsonify({
            'success': True,
            'schedules': result
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== TIME OFF API ==========

@employee_auth_bp.route('/api/employee/<int:employee_id>/time-off', methods=['GET'])
def get_employee_time_off(employee_id):
    """Get employee's time-off requests"""
    import json
    try:
        requests = get_db().execute_query("""
            SELECT
                t.id,
                t.start_date,
                t.end_date,
                t.time_off_type,
                t.is_approved,
                t.notes,
                t.created_at,
                e.name as approved_by_name
            FROM time_off t
            LEFT JOIN employees e ON t.approved_by = e.id
            WHERE t.employee_id = %s
            ORDER BY t.start_date DESC
            LIMIT 20
        """, (employee_id,))

        result = []
        for req in (requests or []):
            status = 'pending'
            if req['is_approved'] == 1:
                status = 'approved'
            elif req['is_approved'] == 0 and req['approved_by_name']:
                status = 'rejected'

            # Parse notes for dates array and reason
            dates = None
            reason = ''
            notes_raw = req['notes'] or ''
            if notes_raw:
                try:
                    notes_data = json.loads(notes_raw)
                    dates = notes_data.get('dates')
                    reason = notes_data.get('reason', '')
                except:
                    reason = notes_raw

            result.append({
                'id': req['id'],
                'start_date': req['start_date'].strftime('%Y-%m-%d'),
                'end_date': req['end_date'].strftime('%Y-%m-%d'),
                'dates': dates,  # Array of individual dates if non-consecutive
                'request_type': req['time_off_type'],
                'status': status,
                'reason': reason,
                'approved_by': req['approved_by_name']
            })

        return jsonify({
            'success': True,
            'requests': result
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/time-off', methods=['POST'])
def request_time_off(employee_id):
    """Submit a time-off request"""
    import json
    try:
        data = request.json

        # Support both formats: dates array (new) or start_date/end_date (legacy)
        dates = data.get('dates', [])
        if dates and len(dates) > 0:
            # New format: array of dates
            sorted_dates = sorted(dates)
            start_date = sorted_dates[0]
            end_date = sorted_dates[-1]
            # Store individual dates in notes as JSON for non-consecutive days
            notes_data = {
                'dates': sorted_dates,
                'reason': data.get('reason', '')
            }
            notes = json.dumps(notes_data)
        else:
            # Legacy format: start_date and end_date
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            reason = data.get('reason', '')
            notes = json.dumps({'reason': reason}) if reason else ''

        time_off_type = data.get('request_type') or data.get('type', 'vacation')

        if not start_date or not end_date:
            return jsonify({'success': False, 'message': 'At least one date required'}), 400

        valid_types = ['vacation', 'sick', 'personal', 'holiday', 'unpaid', 'other']
        if time_off_type not in valid_types:
            time_off_type = 'other'

        # Insert request (is_approved = NULL means pending)
        get_db().execute_query("""
            INSERT INTO time_off (employee_id, start_date, end_date, time_off_type, notes, is_approved)
            VALUES (%s, %s, %s, %s, %s, NULL)
        """, (employee_id, start_date, end_date, time_off_type, notes))

        return jsonify({
            'success': True,
            'message': 'Time-off request submitted'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/employee/<int:employee_id>/time-off/<int:request_id>', methods=['DELETE'])
def cancel_time_off(employee_id, request_id):
    """Cancel a pending time-off request"""
    try:
        # Only allow canceling pending requests
        result = get_db().execute_one("""
            SELECT is_approved FROM time_off
            WHERE id = %s AND employee_id = %s
        """, (request_id, employee_id))

        if not result:
            return jsonify({'success': False, 'message': 'Request not found'}), 404

        if result['is_approved'] is not None:
            return jsonify({'success': False, 'message': 'Cannot cancel approved/denied requests'}), 400

        get_db().execute_query("""
            DELETE FROM time_off WHERE id = %s AND employee_id = %s
        """, (request_id, employee_id))

        return jsonify({
            'success': True,
            'message': 'Request cancelled'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ========== MANAGER TIME-OFF APPROVAL API ==========

@employee_auth_bp.route('/api/manager/time-off/pending', methods=['GET'])
def get_all_pending_time_off():
    """Get all pending time-off requests for manager review"""
    import json
    try:
        requests = get_db().execute_query("""
            SELECT
                t.id,
                t.employee_id,
                e.name as employee_name,
                t.start_date,
                t.end_date,
                t.time_off_type,
                t.notes,
                t.created_at
            FROM time_off t
            JOIN employees e ON t.employee_id = e.id
            WHERE t.is_approved IS NULL
            ORDER BY t.start_date ASC
        """)

        result = []
        for req in (requests or []):
            # Parse notes for dates array and reason
            dates = None
            reason = ''
            notes_raw = req['notes'] or ''
            if notes_raw:
                try:
                    notes_data = json.loads(notes_raw)
                    dates = notes_data.get('dates')
                    reason = notes_data.get('reason', '')
                except:
                    reason = notes_raw

            result.append({
                'id': req['id'],
                'employee_id': req['employee_id'],
                'employee_name': req['employee_name'],
                'start_date': req['start_date'].strftime('%Y-%m-%d'),
                'end_date': req['end_date'].strftime('%Y-%m-%d'),
                'dates': dates,
                'request_type': req['time_off_type'],
                'reason': reason,
                'created_at': req['created_at'].strftime('%Y-%m-%d %H:%M') if req['created_at'] else None
            })

        return jsonify({
            'success': True,
            'requests': result,
            'count': len(result)
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/manager/time-off/<int:request_id>/approve', methods=['PUT'])
def approve_time_off(request_id):
    """Approve a time-off request"""
    try:
        data = request.json or {}
        approved_by = data.get('approved_by')  # Optional - can be NULL

        # If approved_by provided, validate it exists
        if approved_by:
            get_db().execute_query("""
                UPDATE time_off
                SET is_approved = 1, approved_by = %s
                WHERE id = %s AND is_approved IS NULL
            """, (approved_by, request_id))
        else:
            # Approve without setting approved_by (leave as NULL)
            get_db().execute_query("""
                UPDATE time_off
                SET is_approved = 1
                WHERE id = %s AND is_approved IS NULL
            """, (request_id,))

        return jsonify({
            'success': True,
            'message': 'Time-off request approved'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/manager/time-off/<int:request_id>/reject', methods=['PUT'])
def reject_time_off(request_id):
    """Reject a time-off request"""
    try:
        data = request.json or {}
        approved_by = data.get('approved_by')  # Optional - can be NULL

        # If approved_by provided, validate it exists
        if approved_by:
            get_db().execute_query("""
                UPDATE time_off
                SET is_approved = 0, approved_by = %s
                WHERE id = %s AND is_approved IS NULL
            """, (approved_by, request_id))
        else:
            # Reject without setting approved_by
            get_db().execute_query("""
                UPDATE time_off
                SET is_approved = 0
                WHERE id = %s AND is_approved IS NULL
            """, (request_id,))

        return jsonify({
            'success': True,
            'message': 'Time-off request rejected'
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@employee_auth_bp.route('/api/manager/time-off/history', methods=['GET'])
def get_time_off_history():
    """Get history of all time-off decisions (approved and denied)"""
    import json
    try:
        requests = get_db().execute_query("""
            SELECT
                t.id,
                t.employee_id,
                e.name as employee_name,
                t.start_date,
                t.end_date,
                t.time_off_type,
                t.notes,
                t.is_approved,
                t.created_at
            FROM time_off t
            JOIN employees e ON t.employee_id = e.id
            WHERE t.is_approved IS NOT NULL
            ORDER BY t.created_at DESC
            LIMIT 50
        """)

        result = []
        for req in (requests or []):
            dates = None
            reason = ''
            notes_raw = req['notes'] or ''
            if notes_raw:
                try:
                    notes_data = json.loads(notes_raw)
                    dates = notes_data.get('dates')
                    reason = notes_data.get('reason', '')
                except:
                    reason = notes_raw

            result.append({
                'id': req['id'],
                'employee_id': req['employee_id'],
                'employee_name': req['employee_name'],
                'start_date': req['start_date'].strftime('%Y-%m-%d'),
                'end_date': req['end_date'].strftime('%Y-%m-%d'),
                'dates': dates,
                'request_type': req['time_off_type'],
                'reason': reason,
                'status': 'approved' if req['is_approved'] == 1 else 'denied',
                'created_at': req['created_at'].strftime('%Y-%m-%d %H:%M') if req['created_at'] else None
            })

        return jsonify({
            'success': True,
            'history': result
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@employee_auth_bp.route('/api/manager/time-off/approved', methods=['GET'])
def get_approved_time_off():
    """Get all approved time-off for schedule overlay"""
    import json
    try:
        # Get approved time-off for the next 30 days
        requests = get_db().execute_query("""
            SELECT
                t.id,
                t.employee_id,
                e.name as employee_name,
                t.start_date,
                t.end_date,
                t.time_off_type,
                t.notes
            FROM time_off t
            JOIN employees e ON t.employee_id = e.id
            WHERE t.is_approved = 1
              AND t.end_date >= CURDATE()
              AND t.start_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
            ORDER BY t.start_date ASC
        """)

        result = []
        for req in (requests or []):
            dates = None
            notes_raw = req['notes'] or ''
            if notes_raw:
                try:
                    notes_data = json.loads(notes_raw)
                    dates = notes_data.get('dates')
                except:
                    pass

            result.append({
                'id': req['id'],
                'employee_id': req['employee_id'],
                'employee_name': req['employee_name'],
                'start_date': req['start_date'].strftime('%Y-%m-%d'),
                'end_date': req['end_date'].strftime('%Y-%m-%d'),
                'dates': dates,
                'request_type': req['time_off_type']
            })

        return jsonify({
            'success': True,
            'time_off': result
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
