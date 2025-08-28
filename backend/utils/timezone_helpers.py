# backend/utils/timezone_helpers.py

from datetime import datetime, date, time, timedelta
import pytz

class TimezoneHelper:
    """Helper class for timezone conversions and date filtering"""
    
    def __init__(self):
        self.central_tz = pytz.timezone('America/Chicago')
        self.utc_tz = pytz.UTC
    
    def ct_date_to_utc_range(self, ct_date):
        """
        Convert a Central Time date to UTC datetime range
        
        Args:
            ct_date: Can be string 'YYYY-MM-DD' or datetime.date object
        
        Returns:
            tuple: (start_utc, end_utc) as datetime objects
        
        Example:
            '2025-08-27' -> (2025-08-27 05:00:00 UTC, 2025-08-28 04:59:59 UTC)
        """
        # Convert string to date if needed
        if isinstance(ct_date, str):
            ct_date = datetime.strptime(ct_date, '%Y-%m-%d').date()
        
        # Create CT datetime at midnight
        ct_start = self.central_tz.localize(
            datetime.combine(ct_date, time(0, 0, 0))
        )
        ct_end = self.central_tz.localize(
            datetime.combine(ct_date + timedelta(days=1), time(0, 0, 0))
        )
        
        # Convert to UTC
        utc_start = ct_start.astimezone(self.utc_tz)
        utc_end = ct_end.astimezone(self.utc_tz) - timedelta(seconds=1)
        
        return utc_start, utc_end
    
    def utc_to_ct(self, utc_dt):
        """Convert UTC datetime to Central Time"""
        if utc_dt is None:
            return None
        if utc_dt.tzinfo is None:
            utc_dt = self.utc_tz.localize(utc_dt)
        return utc_dt.astimezone(self.central_tz)
    
    def ct_to_utc(self, ct_dt):
        """Convert Central Time to UTC"""
        if ct_dt is None:
            return None
        if ct_dt.tzinfo is None:
            ct_dt = self.central_tz.localize(ct_dt)
        return ct_dt.astimezone(self.utc_tz)
    
    def format_for_display(self, utc_dt):
        """Format UTC datetime for Central Time display"""
        if utc_dt is None:
            return None
        ct_dt = self.utc_to_ct(utc_dt)
        return ct_dt.strftime('%Y-%m-%d %I:%M %p CT')
    
    def get_current_ct_date(self):
        """Get current date in Central Time"""
        return datetime.now(self.central_tz).date()
    
    def is_dst(self, check_date=None):
        """Check if date is in Daylight Saving Time"""
        if check_date is None:
            check_date = self.get_current_ct_date()
        
        if isinstance(check_date, str):
            check_date = datetime.strptime(check_date, '%Y-%m-%d').date()
        
        ct_dt = self.central_tz.localize(
            datetime.combine(check_date, time(12, 0, 0))
        )
        return bool(ct_dt.dst())


# backend/api/dashboard_fixed.py

from flask import Blueprint, request, jsonify
from database.db_manager import get_db
from utils.timezone_helpers import TimezoneHelper
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)
db = get_db()
tz_helper = TimezoneHelper()

@dashboard_bp.route('/api/dashboard/daily-data', methods=['GET'])
def get_daily_data():
    """Get dashboard data for a specific Central Time date"""
    
    # Get date parameter (defaults to today in CT)
    date_str = request.args.get('date')
    if not date_str:
        date_str = tz_helper.get_current_ct_date().strftime('%Y-%m-%d')
    
    # Convert CT date to UTC range
    utc_start, utc_end = tz_helper.ct_date_to_utc_range(date_str)
    
    # Query clock times within UTC range
    clock_query = """
    SELECT 
        e.id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        ct.total_minutes
    FROM employees e
    JOIN clock_times ct ON e.id = ct.employee_id
    WHERE ct.clock_in >= %s AND ct.clock_in < %s
    ORDER BY e.name, ct.clock_in
    """
    
    clock_results = db.fetch_all(clock_query, (utc_start, utc_end))
    
    # Query activities within UTC range
    activity_query = """
    SELECT 
        e.id,
        e.name,
        COUNT(al.id) as activity_count,
        SUM(al.items_count) as total_items,
        MIN(al.window_start) as first_activity,
        MAX(al.window_end) as last_activity
    FROM employees e
    JOIN activity_logs al ON e.id = al.employee_id
    WHERE al.window_start >= %s AND al.window_start < %s
    GROUP BY e.id
    """
    
    activity_results = db.fetch_all(activity_query, (utc_start, utc_end))
    
    # Combine results
    employee_data = {}
    
    # Process clock times
    for row in clock_results:
        emp_id = row['id']
        if emp_id not in employee_data:
            employee_data[emp_id] = {
                'name': row['name'],
                'clock_times': [],
                'activities': None
            }
        
        employee_data[emp_id]['clock_times'].append({
            'clock_in': tz_helper.format_for_display(row['clock_in']),
            'clock_out': tz_helper.format_for_display(row['clock_out']),
            'hours_worked': round(row['total_minutes'] / 60, 2) if row['total_minutes'] else 0
        })
    
    # Process activities
    for row in activity_results:
        emp_id = row['id']
        if emp_id not in employee_data:
            employee_data[emp_id] = {
                'name': row['name'],
                'clock_times': [],
                'activities': None
            }
        
        employee_data[emp_id]['activities'] = {
            'count': row['activity_count'],
            'total_items': row['total_items'],
            'first_activity': tz_helper.format_for_display(row['first_activity']),
            'last_activity': tz_helper.format_for_display(row['last_activity'])
        }
    
    return jsonify({
        'date': date_str,
        'utc_range': {
            'start': utc_start.isoformat(),
            'end': utc_end.isoformat()
        },
        'is_dst': tz_helper.is_dst(date_str),
        'employees': list(employee_data.values()),
        'total_employees': len(employee_data)
    })


@dashboard_bp.route('/api/dashboard/date-range', methods=['GET'])
def get_date_range_data():
    """Get data for a date range in Central Time"""
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'start_date and end_date required'}), 400
    
    # Convert date range to UTC
    start_utc, _ = tz_helper.ct_date_to_utc_range(start_date)
    _, end_utc = tz_helper.ct_date_to_utc_range(end_date)
    
    query = """
    SELECT 
        DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) as work_date,
        COUNT(DISTINCT ct.employee_id) as employees,
        SUM(ct.total_minutes) / 60 as total_hours,
        COUNT(DISTINCT al.id) as total_activities,
        SUM(al.items_count) as total_items
    FROM clock_times ct
    LEFT JOIN activity_logs al ON ct.employee_id = al.employee_id
        AND al.window_start >= ct.clock_in
        AND al.window_start <= COALESCE(ct.clock_out, NOW())
    WHERE ct.clock_in >= %s AND ct.clock_in <= %s
    GROUP BY work_date
    ORDER BY work_date
    """
    
    results = db.fetch_all(query, (start_utc, end_utc))
    
    return jsonify({
        'start_date': start_date,
        'end_date': end_date,
        'data': [
            {
                'date': row['work_date'].strftime('%Y-%m-%d'),
                'employees': row['employees'],
                'total_hours': round(float(row['total_hours'] or 0), 2),
                'total_activities': row['total_activities'],
                'total_items': row['total_items']
            }
            for row in results
        ]
    })


# backend/calculations/productivity_calculator_fixed.py

from datetime import datetime
import pytz
from utils.timezone_helpers import TimezoneHelper

class ProductivityCalculatorFixed:
    """Fixed version of productivity calculator with proper timezone handling"""
    
    def __init__(self):
        self.tz_helper = TimezoneHelper()
        self.db = get_db()
    
    def calculate_daily_scores(self, date_str=None):
        """Calculate daily scores for a Central Time date"""
        
        # Get date to calculate
        if date_str is None:
            ct_date = self.tz_helper.get_current_ct_date()
        else:
            ct_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get UTC boundaries for this CT date
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(ct_date)
        
        # Query for calculations using UTC boundaries
        query = """
        SELECT 
            e.id as employee_id,
            e.name,
            -- Clock time data
            MIN(ct.clock_in) as first_clock_in,
            MAX(COALESCE(ct.clock_out, NOW())) as last_clock_out,
            SUM(
                TIMESTAMPDIFF(
                    MINUTE, 
                    ct.clock_in, 
                    COALESCE(ct.clock_out, NOW())
                )
            ) as total_clocked_minutes,
            
            -- Activity data
            COUNT(DISTINCT al.id) as activity_count,
            SUM(al.items_count) as total_items,
            SUM(al.items_count * rc.multiplier) as total_points,
            
            -- Calculate active time from activities
            COUNT(DISTINCT DATE_FORMAT(al.window_start, '%Y-%m-%d %H:%i')) as active_periods
            
        FROM employees e
        LEFT JOIN clock_times ct ON e.id = ct.employee_id
            AND ct.clock_in >= %s 
            AND ct.clock_in < %s
        LEFT JOIN activity_logs al ON e.id = al.employee_id
            AND al.window_start >= %s
            AND al.window_start < %s
        LEFT JOIN role_configs rc ON al.role_id = rc.id
        WHERE ct.id IS NOT NULL  -- Only employees who clocked in
        GROUP BY e.id
        """
        
        results = self.db.fetch_all(
            query, 
            (utc_start, utc_end, utc_start, utc_end)
        )
        
        # Insert or update daily scores
        for row in results:
            active_minutes = row['active_periods'] * 10  # Assume 10 min per period
            efficiency = (active_minutes / row['total_clocked_minutes'] * 100) if row['total_clocked_minutes'] > 0 else 0
            
            upsert_query = """
            INSERT INTO daily_scores (
                employee_id, score_date, items_processed,
                points_earned, active_minutes, clocked_minutes,
                efficiency_rate, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON DUPLICATE KEY UPDATE
                items_processed = VALUES(items_processed),
                points_earned = VALUES(points_earned),
                active_minutes = VALUES(active_minutes),
                clocked_minutes = VALUES(clocked_minutes),
                efficiency_rate = VALUES(efficiency_rate),
                updated_at = NOW()
            """
            
            self.db.execute_query(
                upsert_query,
                (
                    row['employee_id'],
                    ct_date,
                    row['total_items'] or 0,
                    row['total_points'] or 0,
                    active_minutes,
                    row['total_clocked_minutes'] or 0,
                    round(efficiency, 2)
                )
            )
        
        return len(results)