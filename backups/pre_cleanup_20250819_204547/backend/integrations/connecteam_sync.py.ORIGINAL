# backend/integrations/connecteam_sync.py

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import pytz
import os  # Add this for os.getpid() in sync lock methods

from integrations.connecteam_client import ConnecteamClient, ConnecteamShift, ConnecteamEmployee
from database.db_manager import get_db
from database.cache_manager import CacheManager, get_cache_manager
from models.employee import Employee
from calculations.productivity_calculator import ProductivityCalculator

logger = logging.getLogger(__name__)


class ConnecteamSync:
    """Service to sync Connecteam data with productivity system"""
    
    def __init__(self, api_key: str, clock_id: int):
        self.client = ConnecteamClient(api_key, clock_id)
        self.db = get_db()
        self.cache = get_cache_manager()
        self.productivity_calc = ProductivityCalculator()
        self.central_tz = pytz.timezone('America/Chicago')
        self.utc_tz = pytz.UTC
    
    def get_central_date(self):
        """Get current date in Central Time"""
        return datetime.now(self.central_tz).date()
    
    def get_central_datetime(self):
        """Get current datetime in Central Time"""
        return datetime.now(self.central_tz)
    
    def convert_to_central(self, utc_dt):
        """Convert UTC datetime to Central Time"""
        if utc_dt is None:
            return None
        if utc_dt.tzinfo is None:
            utc_dt = self.utc_tz.localize(utc_dt)
        return utc_dt.astimezone(self.central_tz)
    
    def convert_to_utc(self, central_dt):
        """Convert Central Time to UTC"""
        if central_dt is None:
            return None
        if central_dt.tzinfo is None:
            central_dt = self.central_tz.localize(central_dt)
        return central_dt.astimezone(self.utc_tz)
        
    def sync_employees(self) -> Dict[str, int]:
        """Sync Connecteam employees with local database"""
        current_time = self.get_central_datetime()
        logger.info(f"Starting employee sync from Connecteam at {current_time.strftime('%Y-%m-%d %I:%M:%S %p')} CT")
        
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        try:
            # Get all employees from Connecteam
            connecteam_employees = self.client.get_all_employees(include_archived=True)
            stats['total'] = len(connecteam_employees)
            
            # Get current employees from database
            query = "SELECT id, email, connecteam_user_id FROM employees"
            local_employees = self.db.fetch_all(query)
            local_map = {emp['connecteam_user_id']: emp for emp in local_employees if emp['connecteam_user_id']}
            email_map = {emp['email']: emp for emp in local_employees}
            
            for user_id, ct_employee in connecteam_employees.items():
                try:
                    # Skip archived employees unless they exist locally
                    if ct_employee.is_archived and user_id not in local_map:
                        continue
                    
                    # Map Connecteam title to role_id
                    role_id = self._map_title_to_role(ct_employee.title)
                    
                    if user_id in local_map:
                        # Update existing employee
                        self._update_employee(local_map[user_id]['id'], ct_employee, role_id)
                        stats['updated'] += 1
                    elif ct_employee.email in email_map:
                        # Link by email if not linked by user_id
                        self._link_employee(email_map[ct_employee.email]['id'], user_id)
                        stats['updated'] += 1
                    else:
                        # Create new employee
                        self._create_employee(ct_employee, role_id)
                        stats['created'] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing employee {user_id}: {e}")
                    stats['errors'] += 1
            
            logger.info(f"Employee sync complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error in employee sync: {e}")
            stats['errors'] = stats['total']
            return stats
    
    def _map_title_to_role(self, title: str) -> int:
        """Map Connecteam title to role_id"""
        title_lower = title.lower() if title else ""
        
        # Get roles from database
        query = "SELECT id, role_name FROM role_configs"
        roles = self.db.fetch_all(query)
        role_map = {r['role_name'].lower(): r['id'] for r in roles}
        
        # Try exact match first
        if title_lower in role_map:
            return role_map[title_lower]
        
        # Try partial matches
        for role_name, role_id in role_map.items():
            if role_name in title_lower or title_lower in role_name:
                return role_id
        
        # Default to Picker (usually role_id 3)
        return 3
    
    def _create_employee(self, ct_employee: ConnecteamEmployee, role_id: int):
        """Create new employee from Connecteam data"""
        # Note: Removed role_id from insert since you're using activity-based roles
        query = """
        INSERT INTO employees (
            email, name, hire_date, connecteam_user_id,
            is_active, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, NOW(), NOW()
        )
        """
        
        params = (
            ct_employee.email or f"{ct_employee.user_id}@company.com",
            ct_employee.full_name,
            self.get_central_date(),  # Use current date as default hire date
            ct_employee.user_id,
            not ct_employee.is_archived
        )
        
        self.db.execute_query(query, params)
        logger.info(f"Created employee: {ct_employee.full_name}")
    
    def _update_employee(self, employee_id: int, ct_employee: ConnecteamEmployee, role_id: int):
        """Update existing employee with Connecteam data"""
        # Note: Removed role_id update since you're using activity-based roles
        query = """
        UPDATE employees 
        SET name = %s, is_active = %s, 
            connecteam_user_id = %s, updated_at = NOW()
        WHERE id = %s
        """
        
        params = (
            ct_employee.full_name,
            not ct_employee.is_archived,
            ct_employee.user_id,
            employee_id
        )
        
        self.db.execute_query(query, params)
    
    def _link_employee(self, employee_id: int, connecteam_user_id: str):
        """Link existing employee to Connecteam user ID"""
        query = """
        UPDATE employees 
        SET connecteam_user_id = %s, updated_at = NOW()
        WHERE id = %s
        """
        self.db.execute_query(query, (connecteam_user_id, employee_id))
    
    # Replace the sync_todays_shifts method in connecteam_sync.py:

    def sync_todays_shifts(self) -> Dict[str, int]:
        """Sync today's shifts and update clock times"""
        today = self.get_central_date()
        current_time = self.get_central_datetime()
        
        logger.info(f"Syncing shifts for {today} at {current_time.strftime('%I:%M:%S %p')} CT")
        
        stats = {
            'total_shifts': 0,
            'active_shifts': 0,
            'completed_shifts': 0,
            'clock_records_created': 0,
            'clock_records_updated': 0,
            'duplicates_cleaned': 0,
            'errors': 0
        }
        
        try:
            # ALWAYS clean up duplicates first
            stats['duplicates_cleaned'] = self.cleanup_todays_duplicates()
            
            # Get today's shifts from Connecteam
            shifts = self.client.get_todays_shifts()
            stats['total_shifts'] = len(shifts)
            
            # Process each shift
            processed_employees = set()
            
            for shift in shifts:
                try:
                    # Skip if we already processed this employee today
                    # if shift.user_id in processed_employees:
                    #     logger.debug(f"Already processed {shift.employee_name} today, checking for updates only")
                    
                    # Get employee ID from database
                    employee = self._get_employee_by_connecteam_id(shift.user_id)
                    if not employee:
                        logger.warning(f"Employee not found for Connecteam user {shift.user_id}")
                        continue
                    
                    # Convert shift times to Central Time for logging
                    clock_in_central = self.convert_to_central(shift.clock_in)
                    clock_out_central = self.convert_to_central(shift.clock_out) if shift.clock_out else None
                    
                    logger.debug(f"Processing shift for {shift.employee_name}: "
                            f"In: {clock_in_central.strftime('%I:%M %p')} CT, "
                            f"Out: {clock_out_central.strftime('%I:%M %p') if clock_out_central else 'Active'}")
                    
                    # Sync clock time (stores in UTC)
                    record_updated = self._sync_clock_time(employee['id'], shift)
                    
                    if record_updated:
                        stats['clock_records_updated'] += 1
                    else:
                        stats['clock_records_created'] += 1
                    
                    if shift.is_active:
                        stats['active_shifts'] += 1
                        # Update cache with live data
                        self._update_live_cache(employee['id'], shift)
                    else:
                        stats['completed_shifts'] += 1
                    
                    processed_employees.add(shift.user_id)
                    
                except Exception as e:
                    logger.error(f"Error syncing shift for {shift.employee_name}: {e}")
                    stats['errors'] += 1
            
            # Final cleanup check
            final_cleanup = self.cleanup_todays_duplicates()
            if final_cleanup > 0:
                stats['duplicates_cleaned'] += final_cleanup
                logger.warning(f"Had to clean {final_cleanup} more duplicates after sync")
            
            # Update who's working today cache
            self._update_working_today_cache(shifts)
            
            # Log sync to database
            self.db.execute_query("""
                INSERT INTO connecteam_sync_log (sync_type, records_synced, status, details, synced_at)
                VALUES ('shifts', %s, 'success', %s, NOW())
            """, (stats['total_shifts'], json.dumps(stats)))
            
            logger.info(f"Shift sync complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error in shift sync: {e}")
            stats['errors'] = stats['total_shifts']
            
            # Log failed sync
            self.db.execute_query("""
                INSERT INTO connecteam_sync_log (sync_type, records_synced, status, details, synced_at)
                VALUES ('shifts', 0, 'error', %s, NOW())
            """, (str(e),))
            
            return stats
    
    def _get_employee_by_connecteam_id(self, connecteam_user_id: str) -> Optional[Dict]:
        """Get employee from database by Connecteam user ID"""
        # Removed role join since using activity-based roles
        query = """
        SELECT e.*
        FROM employees e
        WHERE e.connecteam_user_id = %s
        """
        return self.db.fetch_one(query, (connecteam_user_id,))
    
    def _sync_clock_time(self, employee_id: int, shift: ConnecteamShift) -> bool:
        """Sync clock time record from Connecteam shift. Returns True if updated, False if created."""
        
        # Convert times for comparison
        clock_in_central = self.convert_to_central(shift.clock_in)
        clock_in_date = clock_in_central.date()
        
        # First, check if we have ANY record for this employee today
        existing_today = self.db.fetch_all(
            """
            SELECT id, clock_in, clock_out, 
                TIMESTAMPDIFF(SECOND, clock_in, %s) as seconds_diff
            FROM clock_times 
            WHERE employee_id = %s 
            AND DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
            ORDER BY ABS(TIMESTAMPDIFF(SECOND, clock_in, %s))
            """,
            (shift.clock_in, employee_id, clock_in_date, shift.clock_in)
        )
        
        if existing_today:
            # Find the closest matching record
            for existing in existing_today:
                seconds_diff = abs(existing['seconds_diff']) if existing['seconds_diff'] is not None else float('inf')
                
                if seconds_diff < 300:  # Within 5 minutes - it's the same shift
                    # Update only if needed
                    if shift.clock_out and not existing['clock_out']:
                        self.db.execute_query(
                            """
                            UPDATE clock_times 
                            SET clock_out = %s, 
                                total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, %s),
                                is_active = FALSE, 
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (shift.clock_out, shift.clock_out, existing['id'])
                        )
                        logger.info(f"Updated clock out for employee {employee_id}")
                    elif shift.is_active and not existing['clock_out']:
                        # Update active status and duration
                        self.db.execute_query(
                            """
                            UPDATE clock_times 
                            SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW()),
                                is_active = TRUE, 
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (existing['id'],)
                        )
                    return True
            
            # Check if this is a legitimate second shift (e.g., after lunch)
            latest_record = max(existing_today, key=lambda x: x['clock_in'])
            if latest_record['clock_out']:
                # Previous shift is complete - this IS a new shift, create it!
                logger.info(f"Employee {employee_id} starting new shift after break")
                # Continue to create new record - DON'T return True
            else:
                # Active shift exists, update clock_out if available
                if shift.clock_out:
                    self.db.execute_query(
                        """
                        UPDATE clock_times
                        SET clock_out = %s,
                            is_active = FALSE,
                            total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, %s),
                            updated_at = NOW()
                        WHERE employee_id = %s
                        AND DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))
                        AND clock_out IS NULL
                        LIMIT 1
                        """,
                        (shift.clock_out, shift.clock_out, employee_id)
                    )
                    logger.info(f"Updated clock_out for employee {employee_id}")
                else:
                    logger.info(f"Employee {employee_id} still working")
                return True
        
        # Create new record only if truly needed
        try:
            # Use INSERT IGNORE to prevent duplicates at database level
            insert_query = """
            INSERT IGNORE INTO clock_times (
                employee_id, clock_in, clock_out, total_minutes,
                is_active, source, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, 'connecteam', NOW(), NOW()
            )
            """
            
            total_minutes = shift.total_minutes if shift.clock_out else 0
            
            result = self.db.execute_query(
                insert_query,
                (
                    employee_id,
                    shift.clock_in,
                    shift.clock_out,
                    total_minutes,
                    shift.is_active
                )
            )
            
            if result == 0:  # No rows inserted (duplicate prevented)
                logger.warning(f"Duplicate clock record prevented for employee {employee_id}")
                return True
            
            logger.info(f"Created new clock record for employee {employee_id}")
            
            # Sync breaks if any
            if shift.breaks and self.db.cursor.lastrowid:
                self._sync_breaks(self.db.cursor.lastrowid, shift.breaks)
            
            return False
            
        except Exception as e:
            logger.error(f"Error creating clock record: {e}")
            if "Duplicate" in str(e):
                return True
            raise e
        
    def cleanup_todays_duplicates(self) -> int:
        """Clean up any duplicate clock records for today before syncing"""
        today = self.get_central_date()
        
        cleanup_query = """
        DELETE ct1 FROM clock_times ct1
        INNER JOIN clock_times ct2
        WHERE ct1.id > ct2.id
        AND ct1.employee_id = ct2.employee_id
        AND ct1.clock_in = ct2.clock_in
        AND DATE(ct1.clock_in) = %s
        """
        
        try:
            # Execute the query and get row count
            result = self.db.execute_query(cleanup_query, (today,))
            
            # Handle different return types
            if isinstance(result, int):
                rows_deleted = result
            elif hasattr(result, '__iter__'):
                # If it returns a list or similar, assume no rows deleted
                rows_deleted = 0
            else:
                rows_deleted = 0
            
            if rows_deleted > 0:
                logger.warning(f"Cleaned up {rows_deleted} duplicate clock records for {today}")
            
            return rows_deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up duplicates: {e}")
            return 0

    def acquire_sync_lock(self) -> bool:
        """Acquire a lock to prevent concurrent syncs"""
        try:
            # Try to insert/update lock
            self.db.execute_query("""
                INSERT INTO sync_locks (id, process_name, locked_at, pid)
                VALUES (1, 'connecteam_sync', NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    locked_at = IF(TIMESTAMPDIFF(MINUTE, locked_at, NOW()) > 10, NOW(), locked_at),
                    pid = IF(TIMESTAMPDIFF(MINUTE, locked_at, NOW()) > 10, %s, pid)
            """, (os.getpid(), os.getpid()))
            
            # Check if we got the lock
            lock = self.db.fetch_one("SELECT pid FROM sync_locks WHERE id = 1")
            return lock and lock['pid'] == os.getpid()
            
        except Exception as e:
            logger.error(f"Error acquiring sync lock: {e}")
            return False

    def release_sync_lock(self):
        """Release the sync lock"""
        try:
            self.db.execute_query(
                "UPDATE sync_locks SET locked_at = NULL WHERE id = 1 AND pid = %s",
                (os.getpid(),)
            )
        except Exception as e:
            logger.error(f"Error releasing sync lock: {e}")

    def cleanup_duplicate_clock_records(self, date: Optional[datetime.date] = None) -> Dict[str, int]:
        """Clean up duplicate clock records while preserving legitimate breaks"""
        if date is None:
            date = self.get_central_date()
        
        logger.info(f"Cleaning up duplicate clock records for {date}")
        
        stats = {
            'duplicates_found': 0,
            'records_removed': 0,
            'breaks_preserved': 0,
            'employees_affected': set()
        }
        
        # Get all clock records for the date
        query = """
        SELECT 
            id, employee_id, clock_in, clock_out, total_minutes
        FROM clock_times
        WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
        ORDER BY employee_id, clock_in
        """
        
        all_records = self.db.fetch_all(query, (date,))
        
        # Group by employee
        employee_records = {}
        for record in all_records:
            emp_id = record['employee_id']
            if emp_id not in employee_records:
                employee_records[emp_id] = []
            employee_records[emp_id].append(record)
        
        # Process each employee's records
        for emp_id, records in employee_records.items():
            if len(records) <= 1:
                continue
            
            # Sort by clock_in time
            records.sort(key=lambda x: x['clock_in'])
            
            # Find true duplicates (clock_ins within 5 minutes)
            i = 0
            while i < len(records) - 1:
                j = i + 1
                records_to_merge = [records[i]]
                
                # Find all records within 5 minutes of the first one
                while j < len(records):
                    time_diff = (records[j]['clock_in'] - records[i]['clock_in']).total_seconds()
                    
                    if time_diff < 300:  # 5 minutes
                        records_to_merge.append(records[j])
                        j += 1
                    else:
                        break
                
                if len(records_to_merge) > 1:
                    # These are duplicates - merge them
                    stats['duplicates_found'] += len(records_to_merge) - 1
                    stats['employees_affected'].add(emp_id)
                    
                    # Keep the record with the most complete data
                    keep_record = records_to_merge[0]
                    for record in records_to_merge[1:]:
                        # If this record has a clock_out but the keeper doesn't, update
                        if record['clock_out'] and not keep_record['clock_out']:
                            self.db.execute_query(
                                "UPDATE clock_times SET clock_out = %s, total_minutes = %s WHERE id = %s",
                                (record['clock_out'], record['total_minutes'], keep_record['id'])
                            )
                            keep_record['clock_out'] = record['clock_out']
                        
                        # Delete the duplicate
                        self.db.execute_query("DELETE FROM clock_times WHERE id = %s", (record['id'],))
                        stats['records_removed'] += 1
                    
                    i = j
                else:
                    # Check if this is a legitimate break
                    if i > 0 and records[i-1]['clock_out'] and records[i-1]['clock_out'] < records[i]['clock_in']:
                        stats['breaks_preserved'] += 1
                    i += 1
        
        stats['employees_affected'] = len(stats['employees_affected'])
        logger.info(f"Cleanup complete: {stats}")
        
        return stats
    
    def _sync_breaks(self, clock_time_id: int, breaks: List[Dict]):
        """Sync break entries for a clock time"""
        for break_data in breaks:
            query = """
            INSERT INTO break_entries (
                clock_time_id, break_start, break_end, 
                duration_minutes, created_at
            ) VALUES (
                %s, %s, %s, %s, NOW()
            )
            """
            
            self.db.execute_query(
                query,
                (
                    clock_time_id,
                    break_data['start'],
                    break_data['end'],
                    break_data['duration_minutes']
                )
            )
    
    def _update_live_cache(self, employee_id: int, shift: ConnecteamShift):
        """Update cache with live shift data"""
        cache_key = f"employee:{employee_id}:live_clock"
        
        # Convert times to Central for cache
        clock_in_central = self.convert_to_central(shift.clock_in)
        
        cache_data = {
            'clock_in': clock_in_central.isoformat(),
            'clock_in_utc': shift.clock_in.isoformat(),
            'total_minutes': shift.total_minutes,
            'is_active': True,
            'last_updated': self.get_central_datetime().isoformat(),
            'last_updated_utc': datetime.now(self.utc_tz).isoformat()
        }
        
        self.cache.set(cache_key, json.dumps(cache_data), ttl=300)  # 5 minute TTL
    
    def _update_working_today_cache(self, shifts: List[ConnecteamShift]):
        """Update cache with who's working today"""
        working_today = []
        currently_working = []
        current_time = self.get_central_datetime()
        
        for shift in shifts:
            employee = self._get_employee_by_connecteam_id(shift.user_id)
            if not employee:
                continue
            
            # Convert times to Central for display
            clock_in_central = self.convert_to_central(shift.clock_in)
            clock_out_central = self.convert_to_central(shift.clock_out) if shift.clock_out else None
            
            working_data = {
                'employee_id': employee['id'],
                'name': shift.employee_name,
                'title': shift.title,
                'clock_in': clock_in_central.isoformat(),
                'clock_out': clock_out_central.isoformat() if clock_out_central else None,
                'clock_in_time': clock_in_central.strftime('%I:%M %p'),
                'clock_out_time': clock_out_central.strftime('%I:%M %p') if clock_out_central else 'Active',
                'total_minutes': shift.total_minutes,
                'hours_worked': f"{int(shift.total_minutes // 60)}:{int(shift.total_minutes % 60):02d}",
                'is_active': shift.is_active
            }
            
            working_today.append(working_data)
            
            if shift.is_active:
                currently_working.append(working_data)
        
        # Cache results
        self.cache.set(
            'working_today',
            json.dumps({
                'data': working_today,
                'updated_at': current_time.isoformat(),
                'count': len(working_today)
            }),
            ttl=60  # 1 minute TTL
        )
        
        self.cache.set(
            'currently_working',
            json.dumps({
                'data': currently_working,
                'updated_at': current_time.isoformat(),
                'count': len(currently_working)
            }),
            ttl=60
        )
        
        logger.info(f"Updated cache: {len(working_today)} working today, {len(currently_working)} currently active")
    
    def sync_shifts_for_date(self, sync_date: datetime.date) -> Dict[str, int]:
        """Sync shifts for a specific date"""
        logger.info(f"Syncing shifts for {sync_date}")
        
        stats = {
            'total_shifts': 0,
            'synced': 0,
            'errors': 0
        }
        
        try:
            # Convert date to string for API
            date_str = sync_date.strftime('%Y-%m-%d')
            shifts = self.client.get_shifts_for_date(date_str)
            stats['total_shifts'] = len(shifts)
            
            for shift in shifts:
                try:
                    employee = self._get_employee_by_connecteam_id(shift.user_id)
                    if employee:
                        self._sync_clock_time(employee['id'], shift)
                        stats['synced'] += 1
                except Exception as e:
                    logger.error(f"Error syncing shift: {e}")
                    stats['errors'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing shifts for {sync_date}: {e}")
            stats['errors'] = stats['total_shifts']
            return stats
    
    def sync_historical_data(self, days_back: int = 30) -> Dict[str, int]:
        """Sync historical shift data"""
        end_date = self.get_central_date()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"Syncing historical data from {start_date} to {end_date}")
        
        stats = {
            'days_processed': 0,
            'shifts_synced': 0,
            'errors': 0
        }
        
        current_date = start_date
        while current_date <= end_date:
            try:
                day_stats = self.sync_shifts_for_date(current_date)
                stats['shifts_synced'] += day_stats['synced']
                stats['errors'] += day_stats['errors']
                stats['days_processed'] += 1
                
                current_date += timedelta(days=1)
                
            except Exception as e:
                logger.error(f"Error processing date {current_date}: {e}")
                stats['errors'] += 1
                current_date += timedelta(days=1)
        
        logger.info(f"Historical sync complete: {stats}")
        return stats
    
    def sync_todays_shifts_with_lock(self) -> Dict[str, int]:
        """Sync with lock to prevent concurrent runs"""
        
        # Check if table exists, create if not
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS sync_locks (
                id INT PRIMARY KEY DEFAULT 1,
                process_name VARCHAR(50),
                locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pid INT,
                CONSTRAINT check_single_row CHECK (id = 1)
            )
        """)
        
        # Acquire lock
        if not self.acquire_sync_lock():
            logger.warning("Another sync is already running, skipping")
            return {'error': 'Sync already in progress'}
        
        try:
            return self.sync_todays_shifts()
        finally:
            self.release_sync_lock()

    def get_live_clocked_minutes(self, employee_id: int) -> Optional[float]:
        """Get live clocked minutes for an employee"""
        # Check cache first
        cache_key = f"employee:{employee_id}:live_clock"
        cached = self.cache.get(cache_key)
        
        if cached:
            data = json.loads(cached)
            return data['total_minutes']
        
        # If not in cache, query Connecteam
        employee = self.db.fetch_one(
            "SELECT connecteam_user_id FROM employees WHERE id = %s",
            (employee_id,)
        )
        
        if not employee or not employee['connecteam_user_id']:
            return None
        
        shifts = self.client.get_todays_shifts()
        for shift in shifts:
            if shift.user_id == employee['connecteam_user_id'] and shift.is_active:
                self._update_live_cache(employee_id, shift)
                return shift.total_minutes
        
        return None
    
    def get_sync_status(self) -> Dict:
        """Get current sync status and statistics"""
        current_time = self.get_central_datetime()
        
        # Get last sync time
        last_sync_query = """
        SELECT MAX(updated_at) as last_sync 
        FROM clock_times 
        WHERE source = 'connecteam'
        AND DATE(updated_at) = %s

        """
        
        last_sync_result = self.db.fetch_one(last_sync_query, (self.get_central_date(),))
        last_sync = last_sync_result['last_sync'] if last_sync_result else None
        
        if last_sync:
            last_sync_central = self.convert_to_central(last_sync)
            minutes_since_sync = (current_time - last_sync_central).total_seconds() / 60
        else:
            last_sync_central = None
            minutes_since_sync = None
        
        # Get today's stats
        stats_query = """
        SELECT 
            COUNT(DISTINCT employee_id) as employees_synced,
            COUNT(*) as shifts_synced,
            SUM(CASE WHEN is_active = TRUE THEN 1 ELSE 0 END) as active_shifts
        FROM clock_times
        WHERE source = 'connecteam'
        AND DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
        """
        
        stats = self.db.fetch_one(stats_query, (self.get_central_date(),))
        
        return {
            'current_time': current_time.isoformat(),
            'last_sync': last_sync_central.isoformat() if last_sync_central else None,
            'minutes_since_sync': round(minutes_since_sync, 1) if minutes_since_sync else None,
            'employees_synced_today': stats['employees_synced'] or 0,
            'shifts_synced_today': stats['shifts_synced'] or 0,
            'active_shifts': stats['active_shifts'] or 0,
            'sync_needed': minutes_since_sync > 10 if minutes_since_sync else True
        }


# Add this to config.py
CONNECTEAM_CONFIG = {
    'API_KEY': '9255ce96-70eb-4982-82ef-fc35a7651428',
    'CLOCK_ID': 7425182,
    'SYNC_INTERVAL': 150,  # 5 minutes
    'ENABLE_AUTO_SYNC': True
}