"""Productivity calculation engine - DYNAMIC VERSION"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from collections import defaultdict
import pytz  # ADD THIS IMPORT
from utils.timezone_helpers import TimezoneHelper
from database.db_manager import get_db, DatabaseManager  # FIX: Import DatabaseManager
from models import Employee, RoleConfig, ActivityLog, DailyScore

logger = logging.getLogger(__name__)

class ProductivityCalculator:
    """Calculate productivity metrics for employees"""
    
    def __init__(self):
        self.db = DatabaseManager()  # FIX: Use DatabaseManager consistently
        self._role_cache = {}
        self._load_role_configs()
        self.central_tz = pytz.timezone('America/Chicago')  # ADD: Store timezone
        self.tz_helper = TimezoneHelper()
        
    def get_central_date(self):
        """Get current date in Central Time"""
        return datetime.now(self.central_tz).date()
    
    def get_central_datetime(self):
        """Get current datetime in Central Time"""
        return datetime.now(self.central_tz)
    
    def convert_utc_to_central(self, utc_dt):
        """Convert UTC datetime to Central Time"""
        if utc_dt.tzinfo is None:
            # Assume naive datetime is UTC
            utc_dt = pytz.UTC.localize(utc_dt)
        return utc_dt.astimezone(self.central_tz)
        
    def _load_role_configs(self):
        """Load role configurations into cache"""
        roles = self.db.execute_query("SELECT * FROM role_configs")
        for role in roles:
            self._role_cache[role['id']] = RoleConfig(**role)
        logger.info(f"Loaded {len(self._role_cache)} role configurations")
    
    def calculate_active_time(self, activities: List[Dict], role_config = None) -> int:
        """
        Calculate active time by subtracting excess idle from clocked time
        Now includes idle time at start and end of day
        """
        if not activities:
            return 0
        
        # Get employee_id from first activity
        employee_id = activities[0].get('employee_id')
        if not employee_id:
            return len(activities) * 10
        
        # Get clocked minutes and clock times for this period
        process_date = activities[0]['window_start']
        if isinstance(process_date, str):
            process_date = datetime.fromisoformat(process_date).date()
        else:
            process_date = process_date.date()
        
        # Get UTC boundaries for the Central Time date
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(process_date)
        
        clock_data = self.db.execute_one(
            """
            SELECT
                MIN(clock_in) as first_clock_in,
                MAX(COALESCE(clock_out, UTC_TIMESTAMP())) as last_clock_out,
                TIMESTAMPDIFF(MINUTE, MIN(clock_in), MAX(COALESCE(clock_out, UTC_TIMESTAMP()))) as total_minutes
            FROM clock_times
            WHERE employee_id = %s
            AND clock_in >= %s
            AND clock_in < %s
            """,
            (employee_id, utc_start, utc_end)
        )
        
        if not clock_data or not clock_data['total_minutes']:
            return len(activities) * 10
        
        total_clocked = clock_data['total_minutes']
        total_excess_idle = 0
        
        # Sort activities by window_start to ensure proper order
        sorted_activities = sorted(activities, key=lambda x: x['window_start'])
        
        # 1. Check idle at START of day
        if clock_data['first_clock_in']:
            first_activity_start = sorted_activities[0]['window_start']
            if isinstance(first_activity_start, str):
                first_activity_start = datetime.fromisoformat(first_activity_start)
            
            clock_in = clock_data['first_clock_in']
            if isinstance(clock_in, str):
                clock_in = datetime.fromisoformat(clock_in)
                
            start_gap = (first_activity_start - clock_in).total_seconds() / 60
            
            # Allow 15 minutes to get settled at start of day
            start_threshold = 15
            if start_gap > start_threshold:
                total_excess_idle += (start_gap - start_threshold)
                logger.debug(f"Start of day idle: {start_gap:.1f} min, excess: {start_gap - start_threshold:.1f} min")
        
        # 2. Check gaps BETWEEN activities (existing logic)
        prev_activity = None
        for activity in sorted_activities:
            if prev_activity:
                prev_end = prev_activity['window_end']
                curr_start = activity['window_start']
                
                if isinstance(prev_end, str):
                    prev_end = datetime.fromisoformat(prev_end)
                if isinstance(curr_start, str):
                    curr_start = datetime.fromisoformat(curr_start)
                
                gap_minutes = (curr_start - prev_end).total_seconds() / 60
                
                # Get PREVIOUS activity's role for threshold
                prev_role_id = prev_activity.get('role_id', 1)
                prev_role = self._role_cache.get(prev_role_id, role_config)
                
                # Calculate threshold based on PREVIOUS activity
                if hasattr(prev_role, 'role_type') and prev_role.role_type == 'batch':
                    # Dynamic threshold for batch work
                    prev_items = prev_activity.get('items_count', 0)
                    expected = prev_role.expected_per_hour if prev_role.expected_per_hour > 0 else 200
                    time_per_item = 60.0 / expected
                    threshold = max(3, float(prev_items) * float(time_per_item) * 1.05)
                else:
                    # Fixed threshold for continuous work
                    threshold = float(getattr(prev_role, 'idle_threshold_minutes', 5.0))
                
                # Calculate excess idle
                if gap_minutes > threshold:
                    excess = gap_minutes - threshold
                    total_excess_idle += excess
                    logger.debug(f"Gap idle: {gap_minutes:.1f} min, threshold: {threshold:.1f}, excess: {excess:.1f}")
            
            prev_activity = activity
        
        # 3. Check idle at END of day
        last_activity = sorted_activities[-1]
        last_activity_end = last_activity['window_end']
        if isinstance(last_activity_end, str):
            last_activity_end = datetime.fromisoformat(last_activity_end)
        
        clock_out = clock_data['last_clock_out']
        if isinstance(clock_out, str):
            clock_out = datetime.fromisoformat(clock_out)
        
        end_gap = (clock_out - last_activity_end).total_seconds() / 60
        
        # Calculate threshold based on LAST activity
        last_role_id = last_activity.get('role_id', 1)
        last_role = self._role_cache.get(last_role_id, role_config)
        
        if hasattr(last_role, 'role_type') and last_role.role_type == 'batch':
            # Dynamic threshold for batch work
            last_items = last_activity.get('items_count', 0)
            expected = last_role.expected_per_hour if last_role.expected_per_hour > 0 else 200
            time_per_item = 60.0 / expected
            end_threshold = max(5, float(last_items) * float(time_per_item) * 1.05)
        else:
            # Fixed threshold for continuous work
            end_threshold = float(getattr(last_role, 'idle_threshold_minutes', 5.0))
        
        # Check if this is actually end of day (they clocked out)
        # clock_out will be different from NOW() if they actually clocked out
        current_time = datetime.now()
        if clock_out < current_time - timedelta(minutes=5):  # They clocked out (not just NOW())
            # This is true end of day - add 15 minutes for cleanup
            end_threshold_with_cleanup = end_threshold + 15
            if end_gap > end_threshold_with_cleanup:
                excess = end_gap - end_threshold_with_cleanup
                total_excess_idle += excess
                logger.debug(f"End of day idle: {end_gap:.1f} min, threshold with cleanup: {end_threshold_with_cleanup:.1f}, excess: {excess:.1f}")
        else:
            # They're still clocked in - use normal threshold
            if end_gap > end_threshold:
                excess = end_gap - end_threshold
                total_excess_idle += excess
                logger.debug(f"End of day idle (still clocked in): {end_gap:.1f} min, threshold: {end_threshold:.1f}, excess: {excess:.1f}")
        
        # Active time = clocked time - total excess idle
        active_minutes = max(0, int(total_clocked - total_excess_idle))
        
        # Log summary for debugging
        logger.info(f"Employee {employee_id}: Clocked {total_clocked} min, "
                    f"Total excess idle {total_excess_idle:.1f} min, "
                    f"Active {active_minutes} min ({active_minutes/total_clocked*100:.1f}%)")
        
        return active_minutes

    def calculate_efficiency(self, active_minutes: int, clocked_minutes: int) -> float:
        """Calculate efficiency rate (active time / clocked time)"""
        if clocked_minutes <= 0:
            return 0.0
        
        efficiency = active_minutes / clocked_minutes
        # Cap at 100% efficiency
        return min(1.0, round(efficiency, 2))
    
    def calculate_daily_points(self, items_processed: int, multiplier: float) -> float:
        """
        Simple calculation: Items × Role Multiplier
        No efficiency, no active time tracking
        """
        return round(items_processed * multiplier, 2)
    
    def process_employee_day(self, employee_id: int, process_date: date = None) -> Dict:
        """Process all calculations for an employee for a specific day"""
        # CHANGE: Use dynamic date if not provided
        if process_date is None:
            process_date = self.get_central_date()
            
        try:
            # Get UTC boundaries for the Central Time date (if not already done)
            utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(process_date)
            
            # Get employee data (removed role_id join since it's activity-based now)
            employee_data = self.db.execute_one(
                """
                SELECT e.* 
                FROM employees e 
                WHERE e.id = %s
                """,
                (employee_id,)
            )
            
            if not employee_data:
                logger.error(f"Employee {employee_id} not found")
                return None
            
            # CHANGE: Get all activities for the day with timezone conversion
            activities = self.db.execute_query(
                """
                SELECT * FROM activity_logs 
                WHERE employee_id = %s 
                AND window_start >= %s
                AND window_start < %s
                ORDER BY window_start
                """,
                (employee_id, utc_start, utc_end)
            )
            
            clock_data = self.db.execute_one(
                """
                SELECT
                    MIN(clock_in) as first_clock_in,
                    MAX(COALESCE(clock_out, UTC_TIMESTAMP())) as last_clock_out,
                    SUM(total_minutes) as total_minutes,  -- USE THE EXISTING COLUMN!
                    SUM(COALESCE(break_minutes, 0)) as total_break_minutes
                FROM clock_times
                WHERE employee_id = %s
                AND clock_in >= %s
                AND clock_in < %s
                """,
                (employee_id, utc_start, utc_end)
            )
            
            # Calculate metrics
            items_processed = sum(a['items_count'] for a in activities)
            
            # Calculate active time with proper idle detection
            if activities:
                # Pass activities with their role_ids to calculate_active_time
                # The method will handle the threshold calculations internally
                active_minutes = self.calculate_active_time(activities, None)
            if activities:
                first_role_id = activities[0].get('role_id', 1)
                role_config = self._role_cache.get(first_role_id, self._role_cache[1])
                active_minutes = self.calculate_active_time(activities, role_config)
            else:
                active_minutes = 0
            
            # Get clocked minutes (minus breaks)
            clocked_minutes = 0
            if clock_data and clock_data['total_minutes']:
                clocked_minutes = clock_data['total_minutes'] - (clock_data['total_break_minutes'] or 0)
            
            # Calculate efficiency
            efficiency_rate = self.calculate_efficiency(active_minutes, clocked_minutes)
            
            # FIXED: Calculate points using ACTIVITY role multipliers
            points_earned_result = self.db.execute_one(
                """
                SELECT COALESCE(SUM(al.items_count * rc.multiplier), 0) as total_points
                FROM activity_logs al
                JOIN role_configs rc ON rc.id = al.role_id
                WHERE al.employee_id = %s
                AND DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = %s
                """,
                (employee_id, process_date)
            )
            points_earned = round(points_earned_result['total_points'], 2)
            
            # Update or create daily score
            self.db.execute_update(
                """
                INSERT INTO daily_scores 
                    (employee_id, score_date, items_processed, active_minutes, 
                    clocked_minutes, efficiency_rate, points_earned)
                VALUES (%s, %s, %s, %s, %s, %s, %s) AS new_vals
                ON DUPLICATE KEY UPDATE
                    items_processed = new_vals.items_processed,
                    active_minutes = new_vals.active_minutes,
                    clocked_minutes = new_vals.clocked_minutes,
                    efficiency_rate = new_vals.efficiency_rate,
                    points_earned = new_vals.points_earned,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (employee_id, process_date, items_processed, active_minutes,
                clocked_minutes, efficiency_rate, points_earned)
            )
            
            # Get primary role from activities
            primary_role = self.db.execute_one(
                """
                SELECT rc.role_name, rc.id as role_id
                FROM activity_logs al
                JOIN role_configs rc ON rc.id = al.role_id
                WHERE al.employee_id = %s
                AND DATE(CONVERT_TZ(al.window_start, '+00:00', 'America/Chicago')) = %s
                GROUP BY rc.id, rc.role_name
                ORDER BY SUM(al.items_count) DESC
                LIMIT 1
                """,
                (employee_id, process_date)
            )
            
            role_name = primary_role['role_name'] if primary_role else 'No Activity'
            role_config = self._role_cache.get(primary_role['role_id'], self._role_cache[1]) if primary_role else self._role_cache[1]
            
            # Check for idle periods
            idle_periods = self.detect_idle_periods(
                employee_id, activities, clock_data, role_config, process_date
            )
            
            result = {
                'employee_id': employee_id,
                'employee_name': employee_data['name'],
                'role': role_name,  # Dynamic based on activities
                'date': process_date,
                'items_processed': items_processed,
                'active_minutes': active_minutes,
                'clocked_minutes': clocked_minutes,
                'efficiency_rate': efficiency_rate,
                'efficiency_percentage': efficiency_rate * 100,
                'points_earned': points_earned,
                'idle_periods': len(idle_periods),
                'activities_count': len(activities)
            }
            
            logger.info(
                f"Processed {employee_data['name']} for {process_date}: "
                f"{items_processed} items, {efficiency_rate*100:.1f}% efficiency, "
                f"{points_earned} points"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing employee {employee_id} for {process_date}: {str(e)}")
            raise
    
    def detect_idle_periods(self, employee_id: int, activities: List[Dict], 
                           clock_data: Dict, role_config: RoleConfig, 
                           process_date: date) -> List[Dict]:
        """Detect idle periods based on role-specific thresholds"""
        idle_periods = []
        
        if not clock_data or not clock_data['first_clock_in']:
            return idle_periods
        
        # Convert activities to timeline with Central Time
        activity_timeline = []
        for activity in activities:
            window_start = activity['window_start']
            window_end = activity['window_end']
            
            # Convert to datetime if string
            if isinstance(window_start, str):
                window_start = datetime.fromisoformat(window_start)
            if isinstance(window_end, str):
                window_end = datetime.fromisoformat(window_end)
            
            # Convert to Central Time
            window_start_central = self.convert_utc_to_central(window_start)
            window_end_central = self.convert_utc_to_central(window_end)
            
            activity_timeline.append({
                'start': window_start_central,
                'end': window_end_central,
                'items': activity['items_count'],
                'role_config': role_config  # Added for threshold calculation
            })
        
        # Sort by start time
        activity_timeline.sort(key=lambda x: x['start'])
        
        # Check for gaps between activities
        for i in range(1, len(activity_timeline)):
            prev_activity = activity_timeline[i-1]
            curr_activity = activity_timeline[i]
            prev_end = prev_activity['end']
            curr_start = curr_activity['start']
            
            gap_minutes = (curr_start - prev_end).total_seconds() / 60
            
            # Use PREVIOUS activity's threshold (FIXED)
            prev_role_config = prev_activity.get('role_config', role_config)
            threshold = prev_role_config.idle_threshold_minutes if prev_role_config else 5
            
            if gap_minutes > threshold:
                # Record idle period
                idle_period = {
                    'employee_id': employee_id,
                    'start_time': prev_end,
                    'end_time': curr_start,
                    'duration_minutes': int(gap_minutes),
                    'threshold_minutes': threshold
                }
                idle_periods.append(idle_period)
                
                # Insert into database
                self.db.execute_update(
                    """
                    INSERT INTO idle_periods 
                        (employee_id, start_time, end_time, duration_minutes)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (employee_id, prev_end, curr_start, int(gap_minutes))
                )
        
        # Check for idle at start of day
        if activity_timeline and clock_data['first_clock_in']:
            first_activity = activity_timeline[0]['start']
            clock_in = clock_data['first_clock_in']
            
            if isinstance(clock_in, str):
                clock_in = datetime.fromisoformat(clock_in)
            
            # Convert clock in to Central Time
            clock_in_central = self.convert_utc_to_central(clock_in)
            
            start_gap = (first_activity - clock_in_central).total_seconds() / 60
            if start_gap > role_config.idle_threshold_minutes:
                idle_periods.append({
                    'employee_id': employee_id,
                    'start_time': clock_in_central,
                    'end_time': first_activity,
                    'duration_minutes': int(start_gap),
                    'type': 'start_of_day'
                })
        
        return idle_periods
    
    def process_all_employees_for_date(self, process_date: date = None) -> Dict:
        """Process all active employees for a specific date"""
        if process_date is None:
            process_date = self.get_central_date()
        
        # Get UTC boundaries for the Central Time date
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(process_date)
        
        # Get all active employees who worked on this Central Time date
        employees = self.db.execute_query(
            """
            SELECT DISTINCT e.id, e.name 
            FROM employees e
            JOIN clock_times ct ON ct.employee_id = e.id
            WHERE e.is_active = TRUE
            AND ct.clock_in >= %s
            AND ct.clock_in < %s
            """,
            (utc_start, utc_end)
        )
        
        results = {
            'date': process_date,
            'total_employees': len(employees),
            'processed': 0,
            'errors': 0,
            'employee_results': []
        }
        
        for employee in employees:
            try:
                result = self.process_employee_day(employee['id'], process_date)
                if result:
                    results['employee_results'].append(result)
                    results['processed'] += 1
            except Exception as e:
                logger.error(f"Failed to process {employee['name']}: {str(e)}")
                results['errors'] += 1
        
        logger.info(
            f"Processed {results['processed']} employees for {process_date} "
            f"({results['errors']} errors)"
        )
        
        return results
    
    def calculate_today_scores(self):
        """Calculate scores for today (called by scheduler)"""
        today = self.get_central_date()
        logger.info(f"Starting daily score calculation for {today}")
        return self.process_all_employees_for_date(today)

    def process_all_employees_for_date_batch(self, process_date: date) -> Dict:
        """
        BATCH method for fast historical recalculation.
        Uses only 3 queries instead of N queries per employee.

        Performance: ~15s per day vs ~51min for 50 employees

        CRITICAL: Only for historical dates (not today)
        """
        # Safety check - only for historical dates
        today = self.get_central_date()
        if process_date >= today:
            raise ValueError(f"Batch method only for historical dates. Got {process_date}, today is {today}")

        logger.info(f"Starting BATCH processing for {process_date}")
        start_time = datetime.now()

        # Get UTC boundaries for the Central Time date
        utc_start, utc_end = self.tz_helper.ct_date_to_utc_range(process_date)

        # QUERY 1: All employees who worked on this date with their clock data
        logger.info("Query 1: Fetching employees and clock data...")
        employees_clock = self.db.execute_query(
            """
            SELECT
                e.id as employee_id,
                e.name as employee_name,
                MIN(ct.clock_in) as first_clock_in,
                MAX(COALESCE(ct.clock_out, UTC_TIMESTAMP())) as last_clock_out,
                SUM(ct.total_minutes) as total_minutes,
                SUM(COALESCE(ct.break_minutes, 0)) as total_break_minutes
            FROM employees e
            JOIN clock_times ct ON ct.employee_id = e.id
            WHERE e.is_active = TRUE
            AND ct.clock_in >= %s
            AND ct.clock_in < %s
            GROUP BY e.id, e.name
            """,
            (utc_start, utc_end)
        )

        if not employees_clock:
            logger.warning(f"No employees worked on {process_date}")
            return {
                'date': process_date,
                'total_employees': 0,
                'processed': 0,
                'errors': 0,
                'employee_results': [],
                'duration_seconds': 0
            }

        logger.info(f"Found {len(employees_clock)} employees")

        # QUERY 2: All activities for this date with role data
        logger.info("Query 2: Fetching all activities...")
        activities = self.db.execute_query(
            """
            SELECT
                al.employee_id,
                al.items_count,
                al.window_start,
                al.window_end,
                al.role_id,
                rc.multiplier,
                rc.role_name,
                rc.role_type,
                rc.expected_per_hour,
                rc.idle_threshold_minutes
            FROM activity_logs al
            JOIN role_configs rc ON rc.id = al.role_id
            WHERE al.window_start >= %s
            AND al.window_start < %s
            ORDER BY al.employee_id, al.window_start
            """,
            (utc_start, utc_end)
        )

        logger.info(f"Found {len(activities)} activities")

        # Build memory lookups
        activities_by_employee = defaultdict(list)
        for activity in activities:
            activities_by_employee[activity['employee_id']].append(activity)

        # Process each employee in memory
        daily_scores = []
        results = {
            'date': process_date,
            'total_employees': len(employees_clock),
            'processed': 0,
            'errors': 0,
            'employee_results': []
        }

        for emp_clock in employees_clock:
            try:
                employee_id = emp_clock['employee_id']
                employee_name = emp_clock['employee_name']
                emp_activities = activities_by_employee.get(employee_id, [])

                # Calculate items_processed
                items_processed = sum(a['items_count'] for a in emp_activities)

                # Calculate points_earned
                points_earned = sum(a['items_count'] * a['multiplier'] for a in emp_activities)
                points_earned = round(points_earned, 2)

                # Calculate clocked_minutes (minus breaks) - convert Decimal to float
                clocked_minutes = float(emp_clock['total_minutes'] or 0) - float(emp_clock['total_break_minutes'] or 0)

                # Calculate active_minutes (simplified idle detection)
                if emp_activities and clocked_minutes > 0:
                    # Sort activities by window_start
                    sorted_activities = sorted(emp_activities, key=lambda x: x['window_start'])

                    total_excess_idle = 0

                    # 1. Start of day idle
                    first_activity_start = sorted_activities[0]['window_start']
                    if isinstance(first_activity_start, str):
                        first_activity_start = datetime.fromisoformat(first_activity_start)

                    clock_in = emp_clock['first_clock_in']
                    if isinstance(clock_in, str):
                        clock_in = datetime.fromisoformat(clock_in)

                    start_gap = (first_activity_start - clock_in).total_seconds() / 60
                    if start_gap > 15:  # 15 min threshold for start
                        total_excess_idle += (start_gap - 15)

                    # 2. Gaps between activities
                    prev_activity = None
                    for activity in sorted_activities:
                        if prev_activity:
                            prev_end = prev_activity['window_end']
                            curr_start = activity['window_start']

                            if isinstance(prev_end, str):
                                prev_end = datetime.fromisoformat(prev_end)
                            if isinstance(curr_start, str):
                                curr_start = datetime.fromisoformat(curr_start)

                            gap_minutes = (curr_start - prev_end).total_seconds() / 60

                            # Calculate threshold based on PREVIOUS activity
                            if prev_activity.get('role_type') == 'batch':
                                prev_items = prev_activity.get('items_count', 0)
                                expected = prev_activity.get('expected_per_hour', 200)
                                if expected <= 0:
                                    expected = 200
                                time_per_item = 60.0 / expected
                                threshold = max(3, float(prev_items) * float(time_per_item) * 1.05)
                            else:
                                threshold = float(prev_activity.get('idle_threshold_minutes', 5.0))

                            if gap_minutes > threshold:
                                total_excess_idle += (gap_minutes - threshold)

                        prev_activity = activity

                    # 3. End of day idle
                    last_activity = sorted_activities[-1]
                    last_activity_end = last_activity['window_end']
                    if isinstance(last_activity_end, str):
                        last_activity_end = datetime.fromisoformat(last_activity_end)

                    clock_out = emp_clock['last_clock_out']
                    if isinstance(clock_out, str):
                        clock_out = datetime.fromisoformat(clock_out)

                    end_gap = (clock_out - last_activity_end).total_seconds() / 60

                    # Calculate threshold based on LAST activity
                    if last_activity.get('role_type') == 'batch':
                        last_items = last_activity.get('items_count', 0)
                        expected = last_activity.get('expected_per_hour', 200)
                        if expected <= 0:
                            expected = 200
                        time_per_item = 60.0 / expected
                        end_threshold = max(5, float(last_items) * float(time_per_item) * 1.05)
                    else:
                        end_threshold = float(last_activity.get('idle_threshold_minutes', 5.0))

                    # Add 15 min for cleanup at end of day
                    end_threshold_with_cleanup = end_threshold + 15
                    if end_gap > end_threshold_with_cleanup:
                        total_excess_idle += (end_gap - end_threshold_with_cleanup)

                    # Calculate active_minutes
                    active_minutes = max(0, int(clocked_minutes - total_excess_idle))
                else:
                    active_minutes = 0

                # Calculate efficiency_rate
                efficiency_rate = 0.0
                if clocked_minutes > 0:
                    efficiency_rate = min(1.0, round(active_minutes / clocked_minutes, 2))

                # Get primary role name
                role_name = 'No Activity'
                if emp_activities:
                    # Find role with most items
                    role_items = defaultdict(lambda: {'items': 0, 'name': ''})
                    for a in emp_activities:
                        role_id = a['role_id']
                        role_items[role_id]['items'] += a['items_count']
                        role_items[role_id]['name'] = a['role_name']

                    primary_role = max(role_items.items(), key=lambda x: x[1]['items'])
                    role_name = primary_role[1]['name']

                # Add to batch insert list
                daily_scores.append((
                    employee_id,
                    process_date,
                    items_processed,
                    active_minutes,
                    clocked_minutes,
                    efficiency_rate,
                    points_earned
                ))

                # Add to results
                results['employee_results'].append({
                    'employee_id': employee_id,
                    'employee_name': employee_name,
                    'role': role_name,
                    'date': process_date,
                    'items_processed': items_processed,
                    'active_minutes': active_minutes,
                    'clocked_minutes': clocked_minutes,
                    'efficiency_rate': efficiency_rate,
                    'efficiency_percentage': efficiency_rate * 100,
                    'points_earned': points_earned,
                    'activities_count': len(emp_activities)
                })

                results['processed'] += 1

            except Exception as e:
                logger.error(f"Error processing employee {emp_clock['employee_name']}: {str(e)}")
                results['errors'] += 1

        # QUERY 3: Batch INSERT all daily_scores in ONE query
        if daily_scores:
            logger.info(f"Query 3: Batch inserting {len(daily_scores)} daily scores...")

            # Build multi-row INSERT
            values_placeholder = ', '.join(['(%s, %s, %s, %s, %s, %s, %s)'] * len(daily_scores))
            flat_values = [val for score in daily_scores for val in score]

            self.db.execute_update(
                f"""
                INSERT INTO daily_scores
                    (employee_id, score_date, items_processed, active_minutes,
                    clocked_minutes, efficiency_rate, points_earned)
                VALUES {values_placeholder}
                AS new_vals
                ON DUPLICATE KEY UPDATE
                    items_processed = new_vals.items_processed,
                    active_minutes = new_vals.active_minutes,
                    clocked_minutes = new_vals.clocked_minutes,
                    efficiency_rate = new_vals.efficiency_rate,
                    points_earned = new_vals.points_earned,
                    updated_at = CURRENT_TIMESTAMP
                """,
                flat_values
            )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        results['duration_seconds'] = duration

        logger.info(
            f"BATCH processed {results['processed']} employees for {process_date} "
            f"in {duration:.1f}s ({results['errors']} errors)"
        )

        return results