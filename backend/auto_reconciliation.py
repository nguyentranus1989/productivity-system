#!/usr/bin/env python3
"""
Automatic reconciliation that trusts Connecteam completely
Deletes and reimports any day with discrepancies
"""

import sys
import os
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
from datetime import datetime, timedelta
import pytz
import logging
import mysql.connector
import json
from typing import Dict, List, Set

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoFixReconciliation:
    REDIS_KEY = 'reconciliation:last_run'

    def __init__(self):
        self.client = ConnecteamClient(
            api_key="9255ce96-70eb-4982-82ef-fc35a7651428",
            clock_id=7425182
        )

        self.db_config = {
            'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
            'port': 25060,
            'user': 'doadmin',
            'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
            'database': 'productivity_tracker'
        }

        self.utc_tz = pytz.UTC
        self.central_tz = pytz.timezone('America/Chicago')

        # Initialize Redis connection for status tracking
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
                self.redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis not available for status tracking: {e}")
                self.redis_client = None

    def _save_status(self, stats: Dict, days_back: int, success: bool, error: str = None):
        """Save reconciliation run status to Redis"""
        if not self.redis_client:
            return

        try:
            status = {
                'last_run': datetime.now(self.central_tz).isoformat(),
                'days_back': days_back,
                'success': success,
                'days_checked': stats.get('days_checked', 0),
                'days_fixed': stats.get('days_fixed', 0),
                'total_deleted': stats.get('total_deleted', 0),
                'total_imported': stats.get('total_imported', 0),
                'error': error
            }
            # Store for 14 days (enough to see last run even if it fails)
            self.redis_client.setex(self.REDIS_KEY, 60 * 60 * 24 * 14, json.dumps(status))
            logger.info(f"Reconciliation status saved to Redis")
        except Exception as e:
            logger.warning(f"Failed to save status to Redis: {e}")

    @classmethod
    def get_last_run_status(cls) -> Dict:
        """Get the last reconciliation run status from Redis"""
        if not REDIS_AVAILABLE:
            return {'available': False, 'reason': 'Redis not installed'}

        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            data = r.get(cls.REDIS_KEY)
            if data:
                status = json.loads(data)
                status['available'] = True
                return status
            return {'available': True, 'last_run': None, 'reason': 'Never run'}
        except Exception as e:
            return {'available': False, 'reason': str(e)}
        
    def get_db_connection(self):
        """Get database connection"""
        return mysql.connector.connect(**self.db_config)
    
    def convert_to_utc(self, dt, from_tz=None):
        """Convert any datetime to UTC for storage"""
        if dt is None:
            return None
            
        # If no timezone info, assume it's Central Time from Connecteam
        if dt.tzinfo is None:
            if from_tz:
                dt = from_tz.localize(dt)
            else:
                dt = self.central_tz.localize(dt)
        
        # Convert to UTC
        return dt.astimezone(self.utc_tz)
    
    def get_database_shifts_for_date(self, cursor, date_str):
        """Get all database shifts for a specific date"""
        cursor.execute("""
            SELECT 
                e.connecteam_user_id,
                e.name,
                ct.id,
                ct.clock_in,
                ct.clock_out,
                ct.source
            FROM clock_times ct
            JOIN employees e ON ct.employee_id = e.id
            WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = %s
            ORDER BY e.name, ct.clock_in
        """, (date_str,))
        
        shifts_by_user = {}
        for row in cursor.fetchall():
            user_id = row['connecteam_user_id']
            if user_id not in shifts_by_user:
                shifts_by_user[user_id] = []
            shifts_by_user[user_id].append(row)
        
        return shifts_by_user
    
    def compare_shifts(self, db_shift, ct_shift):
        """
        Compare database shift with Connecteam shift
        Returns True if they match (within reasonable tolerance)
        """
        # Convert Connecteam times to UTC for comparison
        ct_clock_in_utc = self.convert_to_utc(ct_shift.clock_in)
        ct_clock_out_utc = self.convert_to_utc(ct_shift.clock_out) if ct_shift.clock_out else None
        
        # Make database times timezone-aware (they come as naive UTC)
        db_clock_in = db_shift['clock_in']
        if db_clock_in.tzinfo is None:
            db_clock_in = self.utc_tz.localize(db_clock_in)
        
        # Check clock_in (within 10 minute tolerance for minor sync delays)
        time_diff = abs((db_clock_in - ct_clock_in_utc).total_seconds())
        if time_diff > 600:  # More than 10 minutes difference
            return False
        
        # Check clock_out
        db_clock_out = db_shift['clock_out']
        if db_clock_out is not None and db_clock_out.tzinfo is None:
            db_clock_out = self.utc_tz.localize(db_clock_out)
            
        if db_clock_out is None and ct_clock_out_utc is None:
            return True  # Both still clocked in
        elif db_clock_out is None or ct_clock_out_utc is None:
            return False  # One has clock_out, other doesn't
        else:
            time_diff = abs((db_clock_out - ct_clock_out_utc).total_seconds())
            return time_diff <= 600  # Within 10 minutes
    
    def check_day_integrity(self, date_str, cursor):
        """
        Check if a day's data matches between database and Connecteam
        Returns: (has_discrepancies, details)
        """
        logger.info(f"Checking integrity for {date_str}")
        
        # Get shifts from both systems
        db_shifts = self.get_database_shifts_for_date(cursor, date_str)
        ct_shifts = self.client.get_shifts_for_date(date_str)
        
        discrepancies = []
        
        # Build lookup for Connecteam shifts by user
        ct_shifts_by_user = {}
        for shift in ct_shifts:
            # Get user's connecteam_user_id
            cursor.execute("""
                SELECT connecteam_user_id 
                FROM employees 
                WHERE connecteam_user_id = %s
            """, (shift.user_id,))
            
            result = cursor.fetchone()
            if result:
                user_id = result['connecteam_user_id']
                if user_id not in ct_shifts_by_user:
                    ct_shifts_by_user[user_id] = []
                ct_shifts_by_user[user_id].append(shift)
        
        # Check for missing employees in database
        for shift in ct_shifts:
            cursor.execute("""
                SELECT id FROM employees 
                WHERE connecteam_user_id = %s
            """, (shift.user_id,))
            
            if not cursor.fetchone():
                discrepancies.append(f"Employee {shift.employee_name} not in database")
        
        # Check each user's shifts
        all_users = set(db_shifts.keys()) | set(ct_shifts_by_user.keys())
        
        for user_id in all_users:
            db_user_shifts = db_shifts.get(user_id, [])
            ct_user_shifts = ct_shifts_by_user.get(user_id, [])
            
            # Different number of shifts
            if len(db_user_shifts) != len(ct_user_shifts):
                discrepancies.append(
                    f"User {user_id}: {len(db_user_shifts)} DB shifts vs {len(ct_user_shifts)} CT shifts"
                )
                continue
            
            # Check for timezone offset issues (5-hour difference)
            for db_shift in db_user_shifts:
                has_match = False
                
                for ct_shift in ct_user_shifts:
                    if self.compare_shifts(db_shift, ct_shift):
                        has_match = True
                        break
                    
                    # Check for 5-hour offset issue
                    ct_clock_in_utc = self.convert_to_utc(ct_shift.clock_in)
                    
                    # Make db_shift clock_in timezone aware
                    db_clock_in = db_shift['clock_in']
                    if db_clock_in.tzinfo is None:
                        db_clock_in = self.utc_tz.localize(db_clock_in)
                    
                    time_diff_hours = abs((db_clock_in - ct_clock_in_utc).total_seconds() / 3600)
                    
                    if 4.5 <= time_diff_hours <= 5.5:
                        discrepancies.append(
                            f"User {user_id}: 5-hour timezone offset detected"
                        )
                        break
                
                if not has_match:
                    discrepancies.append(
                        f"User {user_id}: No matching shift for {db_shift['clock_in']}"
                    )
        
        return len(discrepancies) > 0, discrepancies
    
    def delete_day_data(self, date_str, cursor):
        """Delete all clock_times for a specific date"""
        # Delete using Central Time date matching
        cursor.execute("""
            DELETE FROM clock_times 
            WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = %s
        """, (date_str,))
        
        deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} entries for {date_str}")
        return deleted_count
    
    def import_day_from_connecteam(self, date_str, cursor):
        """Import all shifts for a day from Connecteam"""
        shifts = self.client.get_shifts_for_date(date_str)
        imported = 0
        skipped = 0
        
        for shift in shifts:
            # Get employee ID
            cursor.execute("""
                SELECT id FROM employees 
                WHERE connecteam_user_id = %s
            """, (shift.user_id,))
            
            employee = cursor.fetchone()
            if not employee:
                logger.warning(f"Skipping shift for unknown employee: {shift.employee_name} ({shift.user_id})")
                skipped += 1
                continue
            
            employee_id = employee['id']
            
            # IMPORTANT: Connecteam returns times in UTC already!
            # No conversion needed - just use them directly
            clock_in_utc = shift.clock_in
            clock_out_utc = shift.clock_out
            
            # Ensure timezone awareness
            if clock_in_utc and clock_in_utc.tzinfo is None:
                clock_in_utc = self.utc_tz.localize(clock_in_utc)
            if clock_out_utc and clock_out_utc.tzinfo is None:
                clock_out_utc = self.utc_tz.localize(clock_out_utc)
            
            # Check for duplicates (shouldn't happen after delete, but be safe)
            cursor.execute("""
                SELECT id FROM clock_times 
                WHERE employee_id = %s 
                AND clock_in = %s
            """, (employee_id, clock_in_utc))
            
            if cursor.fetchone():
                logger.debug(f"Shift already exists for {shift.employee_name} at {clock_in_utc}")
                continue
            
            # Insert the shift with UTC times
            cursor.execute("""
                INSERT INTO clock_times 
                (employee_id, clock_in, clock_out, total_minutes, 
                 is_active, source, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'connecteam', NOW(), NOW())
            """, (
                employee_id, 
                clock_in_utc,
                clock_out_utc,
                (int((clock_out_utc - clock_in_utc).total_seconds() / 60) if clock_out_utc else None),
                shift.is_active
            ))
            
            imported += 1
            logger.debug(f"Imported shift for {shift.employee_name}: {shift.clock_in} CT -> {clock_in_utc} UTC")
        
        logger.info(f"Imported {imported} shifts for {date_str} (skipped {skipped})")
        return imported, skipped
    
    def reconcile_day(self, date_str, cursor, conn):
        """
        Reconcile a single day - delete and reimport if any discrepancies
        """
        has_issues, details = self.check_day_integrity(date_str, cursor)
        
        if has_issues:
            logger.warning(f"Found discrepancies for {date_str}:")
            for detail in details[:5]:  # Show first 5 issues
                logger.warning(f"  - {detail}")
            
            # Delete all data for this day
            deleted = self.delete_day_data(date_str, cursor)
            
            # Reimport from Connecteam
            imported, skipped = self.import_day_from_connecteam(date_str, cursor)
            
            # Commit after each day
            conn.commit()
            
            return {
                'status': 'FIXED',
                'deleted': deleted,
                'imported': imported,
                'skipped': skipped,
                'issues': len(details)
            }
        else:
            logger.info(f"✓ {date_str} is in sync")
            return {'status': 'OK'}
    
    def auto_reconcile(self, days_back=7):
        """
        Main reconciliation function
        Checks and fixes the last N days
        """
        logger.info("=" * 60)
        logger.info(f"AUTOMATIC RECONCILIATION - Last {days_back} days")
        logger.info("=" * 60)
        
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        stats = {
            'days_checked': 0,
            'days_fixed': 0,
            'total_deleted': 0,
            'total_imported': 0
        }
        
        try:
            # Check each day
            for days_ago in range(days_back):
                date = datetime.now() - timedelta(days=days_ago)
                date_str = date.strftime('%Y-%m-%d')
                
                logger.info(f"\nProcessing {date_str}...")
                
                result = self.reconcile_day(date_str, cursor, conn)
                
                stats['days_checked'] += 1
                
                if result['status'] == 'FIXED':
                    stats['days_fixed'] += 1
                    stats['total_deleted'] += result['deleted']
                    stats['total_imported'] += result['imported']
            
            # Final cleanup - remove any orphaned entries older than 30 days with no clock_out
            cursor.execute("""
                DELETE FROM clock_times 
                WHERE clock_out IS NULL 
                AND clock_in < DATE_SUB(NOW(), INTERVAL 30 DAY)
            """)
            
            orphans_deleted = cursor.rowcount
            if orphans_deleted > 0:
                logger.info(f"Cleaned up {orphans_deleted} orphaned entries older than 30 days")
                conn.commit()
            
            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("RECONCILIATION COMPLETE")
            logger.info(f"  Days checked: {stats['days_checked']}")
            logger.info(f"  Days fixed: {stats['days_fixed']}")
            logger.info(f"  Total entries deleted: {stats['total_deleted']}")
            logger.info(f"  Total entries imported: {stats['total_imported']}")
            logger.info("=" * 60)

            # Save successful status to Redis
            self._save_status(stats, days_back, success=True)

        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")
            # Save failed status to Redis
            self._save_status(stats, days_back, success=False, error=str(e))
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def fix_all_historical_data(self):
        """
        One-time fix for all historical data
        Goes back 60 days and fixes everything
        """
        logger.info("FIXING ALL HISTORICAL DATA (60 days)")
        self.auto_reconcile(days_back=60)


if __name__ == "__main__":
    reconciler = AutoFixReconciliation()
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--fix-all':
        # Fix all historical data
        reconciler.fix_all_historical_data()
    else:
        # Normal daily reconciliation (last 7 days)
        reconciler.auto_reconcile(days_back=7)
