from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database.db_manager import get_db
from utils.timezone_helpers import TimezoneHelper
import json
import re

schedule_bp = Blueprint('schedule', __name__)
tz_helper = TimezoneHelper()


def normalize_time(time_str, default='06:00'):
    """Normalize time string to HH:MM format. Handles malformed inputs like '4:30:' or '14:30'."""
    if not time_str:
        return default
    # Remove trailing colons and whitespace
    time_str = str(time_str).strip().rstrip(':')
    # Match HH:MM or H:MM pattern
    match = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match:
        hours, minutes = int(match.group(1)), int(match.group(2))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return f"{hours:02d}:{minutes:02d}"
    return default


# ============================================
# PUBLISH SCHEDULE (New Station-Based Format)
# ============================================

@schedule_bp.route('/api/schedule/publish', methods=['POST'])
def publish_schedule():
    """Publish a weekly schedule from the intelligent scheduler"""
    try:
        data = request.json
        week_start = data.get('week_start')
        schedule_data = data.get('schedule', {})  # { station: { date: [shifts] } }

        if not week_start:
            return jsonify({'success': False, 'message': 'week_start required'}), 400

        db = get_db()

        # Check if schedule for this week already exists
        existing = db.execute_one("""
            SELECT id FROM published_schedules WHERE week_start_date = %s
        """, (week_start,))

        if existing:
            # Update existing - delete old shifts first
            db.execute_query("""
                DELETE FROM published_shifts WHERE schedule_id = %s
            """, (existing['id'],))
            schedule_id = existing['id']

            # Update status
            db.execute_query("""
                UPDATE published_schedules
                SET status = 'published', updated_at = NOW()
                WHERE id = %s
            """, (schedule_id,))
        else:
            # Create new schedule record and get ID directly (no extra SELECT needed)
            schedule_id = db.execute_update("""
                INSERT INTO published_schedules (week_start_date, status, created_by)
                VALUES (%s, 'published', 'Manager')
            """, (week_start,))

        # Collect all employee IDs and validate they exist
        all_employee_ids = set()
        for station_id, dates in schedule_data.items():
            for date_str, shifts in dates.items():
                for shift in shifts:
                    emp_id = shift.get('employee_id')
                    if emp_id:
                        all_employee_ids.add(emp_id)

        # Validate employee IDs exist in database
        if all_employee_ids:
            placeholders = ','.join(['%s'] * len(all_employee_ids))
            valid_employees = db.execute_query(f"""
                SELECT id FROM employees WHERE id IN ({placeholders})
            """, tuple(all_employee_ids))
            valid_ids = {e['id'] for e in (valid_employees or [])}
            invalid_ids = all_employee_ids - valid_ids

            if invalid_ids:
                return jsonify({
                    'success': False,
                    'error': f'Invalid employee IDs: {list(invalid_ids)}. These employees may have been deleted.'
                }), 400

        # Collect all shifts for batch insert (10-20x faster than individual INSERTs)
        shift_values = []
        for station_id, dates in schedule_data.items():
            for date_str, shifts in dates.items():
                for shift in shifts:
                    shift_values.append((
                        schedule_id,
                        shift.get('employee_id'),
                        date_str,
                        station_id,
                        normalize_time(shift.get('start_time'), '06:00'),
                        normalize_time(shift.get('end_time'), '14:30')
                    ))

        # Batch insert all shifts in one query
        if shift_values:
            db.execute_many("""
                INSERT INTO published_shifts
                (schedule_id, employee_id, shift_date, station, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, shift_values)

        return jsonify({
            'success': True,
            'schedule_id': schedule_id,
            'shifts_saved': len(shift_values),
            'message': f'Schedule published with {len(shift_values)} shifts'
        })

    except Exception as e:
        print(f"Error publishing schedule: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schedule_bp.route('/api/schedule/save-draft', methods=['POST'])
def save_draft():
    """Save schedule as draft - optimized for remote DB (minimal roundtrips)"""
    import time
    timings = {}
    t0 = time.time()

    try:
        data = request.json
        week_start = data.get('week_start')
        schedule_data = data.get('schedule', {})

        if not week_start:
            return jsonify({'success': False, 'message': 'week_start required'}), 400

        t1 = time.time()
        db = get_db()
        timings['1_get_db'] = round((time.time() - t1) * 1000)

        # Build shift values first (no DB call needed)
        shift_values = []
        for station_id, dates in schedule_data.items():
            for date_str, shifts in dates.items():
                for shift in shifts:
                    if shift.get('employee_id'):  # Skip empty shifts
                        shift_values.append((
                            shift.get('employee_id'),
                            date_str,
                            station_id,
                            normalize_time(shift.get('start_time'), '06:00'),
                            normalize_time(shift.get('end_time'), '14:30')
                        ))

        # SINGLE QUERY: Upsert schedule + get ID (uses INSERT ON DUPLICATE KEY)
        t1 = time.time()
        schedule_id = db.execute_update("""
            INSERT INTO published_schedules (week_start_date, status, created_by, updated_at)
            VALUES (%s, 'draft', 'Manager', NOW())
            ON DUPLICATE KEY UPDATE status = 'draft', updated_at = NOW()
        """, (week_start,))
        timings['2_upsert'] = round((time.time() - t1) * 1000)

        # If UPDATE happened, schedule_id is 0, need to fetch it
        if not schedule_id:
            t1 = time.time()
            result = db.execute_one("SELECT id FROM published_schedules WHERE week_start_date = %s", (week_start,))
            schedule_id = result['id']
            timings['3_get_id'] = round((time.time() - t1) * 1000)

        # COMBINED: Delete old + Insert new in single transaction (saves 1 roundtrip)
        t1 = time.time()
        db.execute_query("DELETE FROM published_shifts WHERE schedule_id = %s", (schedule_id,))
        if shift_values:
            shift_values_with_id = [(schedule_id,) + v for v in shift_values]
            db.execute_many("""
                INSERT INTO published_shifts
                (schedule_id, employee_id, shift_date, station, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, shift_values_with_id)
        timings['3_delete_insert'] = round((time.time() - t1) * 1000)

        timings['total'] = round((time.time() - t0) * 1000)
        print(f"[TIMING] save_draft: {timings}")

        return jsonify({
            'success': True,
            'schedule_id': schedule_id,
            'shifts_saved': len(shift_values),
            'timings_ms': timings
        })

    except Exception as e:
        print(f"Error saving draft: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schedule_bp.route('/api/schedule/published/<week_date>', methods=['GET'])
def get_published_schedule(week_date):
    """Get published schedule for a specific week (includes drafts for manager view)"""
    try:
        db = get_db()

        # Get schedule status first
        schedule_record = db.execute_one("""
            SELECT id, status FROM published_schedules WHERE week_start_date = %s
        """, (week_date,))

        schedule_status = schedule_record['status'] if schedule_record else None

        # Get schedule and shifts
        shifts = db.execute_query("""
            SELECT
                ps.id as shift_id,
                ps.employee_id,
                e.name as employee_name,
                ps.shift_date,
                ps.station,
                ps.start_time,
                ps.end_time
            FROM published_shifts ps
            JOIN published_schedules pub ON ps.schedule_id = pub.id
            JOIN employees e ON ps.employee_id = e.id
            WHERE pub.week_start_date = %s
            ORDER BY ps.shift_date, ps.station, e.name
        """, (week_date,))

        # Restructure into station-based format
        schedule = {}
        for shift in (shifts or []):
            station = shift['station']
            date_str = shift['shift_date'].strftime('%Y-%m-%d')

            if station not in schedule:
                schedule[station] = {}
            if date_str not in schedule[station]:
                schedule[station][date_str] = []

            schedule[station][date_str].append({
                'employee_id': shift['employee_id'],
                'name': shift['employee_name'],
                'start_time': str(shift['start_time'])[:5] if shift['start_time'] else '06:00',
                'end_time': str(shift['end_time'])[:5] if shift['end_time'] else '14:30'
            })

        return jsonify({
            'success': True,
            'week_start': week_date,
            'schedule': schedule,
            'status': schedule_status,
            'has_schedule': len(shifts or []) > 0
        })

    except Exception as e:
        print(f"Error getting published schedule: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schedule_bp.route('/api/employee/<int:employee_id>/schedule/week', methods=['GET'])
def get_employee_week_schedule(employee_id):
    """Get an employee's schedule for current and next week (format for employee portal)"""
    import json as json_lib
    try:
        db = get_db()
        ct_date = tz_helper.get_current_ct_date()

        # Get Sunday of current week (frontend uses Sun-Sat weeks)
        days_since_sunday = (ct_date.weekday() + 1) % 7
        week_start = ct_date - timedelta(days=days_since_sunday)
        next_week_start = week_start + timedelta(days=7)
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
        """, (employee_id, week_start, two_weeks_end))

        for to in (time_off or []):
            # Check if notes contains specific dates
            specific_dates = None
            if to.get('notes'):
                try:
                    notes_data = json_lib.loads(to['notes'])
                    if isinstance(notes_data, dict) and 'dates' in notes_data:
                        specific_dates = notes_data['dates']
                except (json_lib.JSONDecodeError, TypeError):
                    pass

            if specific_dates:
                for date_str in specific_dates:
                    time_off_dates.add(date_str)
            else:
                current = to['start_date']
                while current <= to['end_date']:
                    time_off_dates.add(current.strftime('%Y-%m-%d'))
                    current += timedelta(days=1)

        # Get shifts for this week and next week (include drafts, use latest schedule per week)
        shifts = db.execute_query("""
            SELECT DISTINCT
                ps.shift_date,
                ps.station,
                ps.start_time,
                ps.end_time
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
        """, (employee_id, week_start, two_weeks_end))

        # Build shift lookup by date (excluding time-off days)
        shift_by_date = {}
        for shift in (shifts or []):
            date_str = shift['shift_date'].strftime('%Y-%m-%d')
            if date_str not in time_off_dates:
                shift_by_date[date_str] = {
                    'shift_start': str(shift['start_time'])[:5] if shift['start_time'] else None,
                    'shift_end': str(shift['end_time'])[:5] if shift['end_time'] else None,
                    'station': shift['station']
                }

        # Build current week array (Sun-Sat)
        current_week = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            date_str = day_date.strftime('%Y-%m-%d')
            shift_info = shift_by_date.get(date_str, {})
            current_week.append({
                'date': date_str,
                'shift_start': shift_info.get('shift_start'),
                'shift_end': shift_info.get('shift_end'),
                'station': shift_info.get('station'),
                'time_off': date_str in time_off_dates
            })

        # Build next week array (Sun-Sat)
        next_week = []
        for i in range(7):
            day_date = next_week_start + timedelta(days=i)
            date_str = day_date.strftime('%Y-%m-%d')
            shift_info = shift_by_date.get(date_str, {})
            next_week.append({
                'date': date_str,
                'shift_start': shift_info.get('shift_start'),
                'shift_end': shift_info.get('shift_end'),
                'station': shift_info.get('station'),
                'time_off': date_str in time_off_dates
            })

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'current_week': current_week,
            'next_week': next_week
        })

    except Exception as e:
        print(f"Error getting employee schedule: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@schedule_bp.route('/api/schedule/save', methods=['POST'])
def save_schedule():
    try:
        data = request.json
        week_start = data.get('week_start', datetime.now().strftime('%Y-%m-%d'))
        schedule_data = data.get('schedule', [])
        print(f'Received data keys: {data.keys()}')
        print(f'Schedule data: {len(schedule_data)} employees')
        
        #         # First check if tables exist, if not create them
        #         create_tables_query = """
        #         CREATE TABLE IF NOT EXISTS schedule_master (
        #             id INT AUTO_INCREMENT PRIMARY KEY,
        #             week_start_date DATE,
        #             status ENUM('draft', 'published', 'sent') DEFAULT 'draft',
        #             created_by VARCHAR(100) DEFAULT 'Lieu',
        #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        #         );
        #         
        #         CREATE TABLE IF NOT EXISTS schedule_details (
        #             id INT AUTO_INCREMENT PRIMARY KEY,
        #             schedule_id INT,
        #             employee_name VARCHAR(100),
        #             monday_time VARCHAR(20),
        #             tuesday_time VARCHAR(20),
        #             wednesday_time VARCHAR(20),
        #             thursday_time VARCHAR(20),
        #             friday_time VARCHAR(20),
        #             saturday_time VARCHAR(20),
        #             sunday_time VARCHAR(20),
        #             FOREIGN KEY (schedule_id) REFERENCES schedule_master(id)
        #         );
        #         """
        #         
        #         # Execute table creation - handle if tables already exist
        #         try:
        #             for statement in create_tables_query.split(";"):
        #                 if statement.strip():
        #                     db.execute_update(statement, None)
        #         except Exception as e:
        #             # Tables might already exist, that is OK
        #             if "already exists" not in str(e).lower():
        #                 raise e
        
        # Insert into schedule_master and get the ID properly
        master_query = """
            INSERT INTO schedule_master (week_start_date, status, created_by)
            VALUES (%s, 'draft', 'Lieu')
        """
        
        # Execute insert - execute_update returns lastrowid
        schedule_id = db.execute_update(master_query, (week_start,))
        
        if not schedule_id:
            raise Exception("Failed to get schedule ID")
        
        print(f"Got schedule_id: {schedule_id}")
        # Insert schedule details
        for employee_schedule in schedule_data:
            try:
                print(f"Saving employee: {employee_schedule}")
                detail_query = """
                    INSERT INTO schedule_details 
                    (schedule_id, employee_name, monday_time, tuesday_time, 
                     wednesday_time, thursday_time, friday_time, saturday_time, sunday_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                times = employee_schedule["times"]
                # Pad times list to 7 days if needed
                while len(times) < 7:
                    times.append("OFF")
                    
                db.execute_update(detail_query, (
                    schedule_id,
                    employee_schedule["employee"],
                    times[0], times[1], times[2], times[3], 
                    times[4], times[5], times[6]
                ))
            except Exception as detail_error:
                print(f"Error saving detail: {detail_error}")
                continue
        
        return jsonify({
            'success': True,
            'schedule_id': schedule_id,
            'message': f'Schedule saved successfully with ID {schedule_id}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schedule_bp.route('/api/schedule/employees', methods=['GET'])
def get_employees():
    try:
        query = "SELECT id, name FROM employees WHERE is_active = 1 ORDER BY name"
        employees = db.fetch_all(query)
        return jsonify({
            'success': True,
            'employees': employees
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schedule_bp.route('/api/schedule/weekly', methods=['GET'])
def get_weekly_schedule():
    """Get weekly schedule data"""
    return jsonify({
        'success': True,
        'schedule': {
            'week_start': '2025-08-12',
            'employees': [],
            'message': 'No schedule data yet'
        }
    })

@schedule_bp.route('/api/schedule/load/<week_date>', methods=['GET'])
def load_schedule(week_date):
    try:
        query = """
            SELECT sm.*, sd.*
            FROM schedule_master sm
            JOIN schedule_details sd ON sm.id = sd.schedule_id
            WHERE sm.week_start_date = %s
            ORDER BY sd.id
        """
        results = db.fetch_all(query, (week_date,))
        
        return jsonify({
            'success': True,
            'schedule': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schedule_bp.route('/api/schedule/predictions/weekly', methods=['GET'])
def get_weekly_predictions():
    """Get real predictions from database"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        query = """
            SELECT
                prediction_date,
                predicted_orders,
                confidence_score,
                DAYNAME(prediction_date) as day_name
            FROM order_predictions
            WHERE prediction_date >= %s
            ORDER BY prediction_date
            LIMIT 7
        """

        results = get_db().execute_query(query, (ct_date,))
        
        predictions = {}
        total = 0
        
        for row in results:
            date_str = row['prediction_date'].strftime('%Y-%m-%d')
            predictions[date_str] = {
                'date': date_str,
                'day_name': row['day_name'],
                'predicted_orders': row['predicted_orders'],
                'confidence': row['confidence_score']
            }
            total += row['predicted_orders']
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'total_predicted': total,
            'daily_average': total // 7 if results else 0
        })
        
    except Exception as e:
        print(f"Error getting predictions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@schedule_bp.route('/api/schedule/employees/all', methods=['GET'])
def get_all_employees():
    """Get all active employees for scheduling"""
    try:
        db = get_db()

        # Simple query - just get active employees
        query = """
            SELECT id, name
            FROM employees
            WHERE is_active = 1
            ORDER BY name
        """

        results = db.execute_query(query)

        employees = []
        for row in (results or []):
            employees.append({
                'id': row['id'],
                'name': row['name'],
                'hours': 0  # Will be calculated client-side from schedule
            })

        return jsonify({
            'success': True,
            'employees': employees,
            'total': len(employees)
        })

    except Exception as e:
        print(f"Error getting employees: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schedule_bp.route('/api/schedule/predictions', methods=['GET'])
def get_predictions_summary():
    """Get predictions summary for scheduling UI"""
    try:
        ct_date = tz_helper.get_current_ct_date()

        query = """
            SELECT
                SUM(predicted_orders) as total_orders,
                AVG(predicted_orders) as avg_daily,
                COUNT(*) as days_count
            FROM predictions_enhanced
            WHERE prediction_date >= %s
              AND prediction_date < DATE_ADD(%s, INTERVAL 7 DAY)
        """

        result = get_db().execute_query(query, (ct_date, ct_date))

        if result and result[0]['total_orders']:
            total = int(result[0]['total_orders'])
            avg_daily = int(result[0]['avg_daily'])
            # Calculate recommended staff (based on ~45 items/person/day)
            recommended_min = max(4, total // 7 // 50)
            recommended_max = max(6, total // 7 // 35)
        else:
            total = 350  # Fallback
            avg_daily = 50
            recommended_min = 8
            recommended_max = 10

        return jsonify({
            'success': True,
            'predicted_orders': f"~{total}",
            'avg_daily': avg_daily,
            'recommended_staff': f"{recommended_min}-{recommended_max}"
        })

    except Exception as e:
        print(f"Error getting predictions: {str(e)}")
        return jsonify({
            'success': True,
            'predicted_orders': '~350',
            'recommended_staff': '8-10'
        })


@schedule_bp.route('/api/dashboard/station-performance', methods=['GET'])
def get_station_performance():
    """Get station performance metrics for staffing view"""
    try:
        ct_date = tz_helper.get_current_ct_date()
        utc_start, utc_end = tz_helper.ct_date_to_utc_range(ct_date)

        # Get today's activity by station
        query = """
            SELECT
                al.activity_type as station,
                COUNT(DISTINCT al.employee_id) as current_staff,
                SUM(al.items_count) as total_items,
                AVG(al.items_count / GREATEST(al.duration_minutes/60, 0.1)) as avg_rate
            FROM activity_logs al
            WHERE al.window_start >= %s AND al.window_start < %s
            GROUP BY al.activity_type
        """

        results = get_db().execute_query(query, (utc_start, utc_end))

        # Station targets
        targets = {
            'heat_press': {'target': 40, 'needed': 2},
            'qc': {'target': 45, 'needed': 2},
            'film': {'target': 133, 'needed': 1},
            'picking': {'target': 200, 'needed': 1},
            'labeling': {'target': 200, 'needed': 1}
        }

        performance = {}
        for row in results:
            station_code = row['station'].lower().replace(' ', '_') if row['station'] else 'other'
            target_info = targets.get(station_code, {'target': 45, 'needed': 1})

            performance[station_code] = {
                'current_staff': row['current_staff'] or 0,
                'needed': target_info['needed'],
                'output': int(row['total_items'] or 0),
                'efficiency': min(100, int((row['avg_rate'] or 0) / target_info['target'] * 100)),
                'target': target_info['target']
            }

        # Add missing stations with defaults
        for code, info in targets.items():
            if code not in performance:
                performance[code] = {
                    'current_staff': 0,
                    'needed': info['needed'],
                    'output': 0,
                    'efficiency': 0,
                    'target': info['target']
                }

        return jsonify(performance)

    except Exception as e:
        print(f"Error getting station performance: {str(e)}")
        return jsonify({})
