#!/usr/bin/env python3
"""
Clean reconciliation script - only syncs missing data from Connecteam
No guessing, no estimates, just pure sync
"""

import sys
import os
sys.path.append('/var/www/productivity-system/backend')

from integrations.connecteam_client import ConnecteamClient
from datetime import datetime, timedelta
import pytz
import logging
import mysql.connector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConnecteamReconciliation:
    def __init__(self):
        # Use your actual working credentials
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
        
        self.central_tz = pytz.timezone('America/Chicago')
        
    def get_db_connection(self):
        """Get database connection"""
        return mysql.connector.connect(**self.db_config)
    
    def find_matching_shift(self, cursor, employee_id, clock_in):
        """
        Find matching shift in database
        Matches by employee + date + hour (with 1 hour tolerance)
        """
        cursor.execute("""
            SELECT id, clock_in, clock_out, total_minutes
            FROM clock_times 
            WHERE employee_id = %s 
            AND DATE(clock_in) = DATE(%s)
            AND ABS(HOUR(clock_in) - HOUR(%s)) <= 1
            LIMIT 1
        """, (employee_id, clock_in, clock_in))
        
        return cursor.fetchone()
    
    def reconcile_date(self, date_str, cursor, conn):
        """Reconcile a single date"""
        stats = {'checked': 0, 'updated': 0, 'added': 0, 'skipped': 0}
        
        # Get all shifts from Connecteam for this date
        shifts = self.client.get_shifts_for_date(date_str)
        logger.info(f"Found {len(shifts)} shifts in Connecteam for {date_str}")
        
        for shift in shifts:
            stats['checked'] += 1
            
            # Get employee ID from database
            cursor.execute("""
                SELECT id, name FROM employees 
                WHERE connecteam_user_id = %s
            """, (shift.user_id,))
            
            employee = cursor.fetchone()
            if not employee:
                logger.warning(f"Employee not found for Connecteam ID: {shift.user_id} ({shift.employee_name})")
                continue
            
            employee_id = employee['id']
            employee_name = employee['name']
            
            # Find matching shift in database
            existing = self.find_matching_shift(cursor, employee_id, shift.clock_in)
            
            if not existing:
                # No match found - INSERT new shift
                cursor.execute("""
                    INSERT INTO clock_times 
                    (employee_id, clock_in, clock_out, total_minutes, 
                     is_active, source, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'connecteam', NOW(), NOW())
                """, (
                    employee_id, 
                    shift.clock_in, 
                    shift.clock_out,  # Can be NULL if still clocked in
                    shift.total_minutes,  # Can be NULL
                    shift.is_active
                ))
                
                stats['added'] += 1
                status = "ADDED"
                logger.info(f"  {status}: {employee_name} - {shift.clock_in} to {shift.clock_out or 'ACTIVE'}")
                
            elif existing['clock_out'] is None and shift.clock_out is not None:
                # Found match with missing clock_out - UPDATE
                cursor.execute("""
                    UPDATE clock_times 
                    SET clock_out = %s,
                        total_minutes = %s,
                        is_active = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (shift.clock_out, shift.total_minutes, shift.is_active, existing['id']))
                
                stats['updated'] += 1
                status = "UPDATED"
                logger.info(f"  {status}: {employee_name} - Added clock_out {shift.clock_out}")
                
            else:
                # Data matches or both show as still clocked in - SKIP
                stats['skipped'] += 1
                # Don't log skips to reduce noise
        
        return stats
    
    def reconcile_last_n_days(self, days=7):
        """Reconcile the last N days"""
        logger.info(f"Starting {days}-day reconciliation...")
        logger.info("=" * 60)
        
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        total_stats = {'checked': 0, 'updated': 0, 'added': 0, 'skipped': 0}
        
        try:
            # Process each day
            for days_ago in range(days):
                date = datetime.now() - timedelta(days=days_ago)
                date_str = date.strftime('%Y-%m-%d')
                
                logger.info(f"\nProcessing {date_str} ({date.strftime('%A')})")
                logger.info("-" * 40)
                
                # Reconcile this date
                day_stats = self.reconcile_date(date_str, cursor, conn)
                
                # Add to totals
                for key in total_stats:
                    total_stats[key] += day_stats[key]
                
                # Show daily summary
                if day_stats['updated'] > 0 or day_stats['added'] > 0:
                    logger.info(f"  Summary: {day_stats['added']} added, {day_stats['updated']} updated, {day_stats['skipped']} skipped")
                
                # Commit after each day
                conn.commit()
            
            # Final summary
            logger.info("\n" + "=" * 60)
            logger.info("RECONCILIATION COMPLETE")
            logger.info(f"  Total shifts checked: {total_stats['checked']}")
            logger.info(f"  New shifts added: {total_stats['added']}")
            logger.info(f"  Clock-outs fixed: {total_stats['updated']}")
            logger.info(f"  Already in sync: {total_stats['skipped']}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during reconciliation: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def show_current_status(self):
        """Show current missing clock-outs"""
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Check for missing clock-outs from past days
            cursor.execute("""
                SELECT e.name, ct.clock_in,
                       TIMESTAMPDIFF(HOUR, ct.clock_in, NOW()) as hours_since
                FROM clock_times ct
                JOIN employees e ON ct.employee_id = e.id
                WHERE ct.clock_out IS NULL 
                AND DATE(ct.clock_in) < CURDATE()
                ORDER BY ct.clock_in
            """)
            
            missing = cursor.fetchall()
            
            if missing:
                print("\n⚠️  EMPLOYEES STILL SHOWING AS CLOCKED IN:")
                print("-" * 60)
                print(f"{'Employee':<25} {'Clock In':<20} {'Hours Ago':<10}")
                print("-" * 60)
                
                for record in missing:
                    print(f"{record['name']:<25} {str(record['clock_in']):<20} {record['hours_since']:<10}")
                
                print(f"\nTotal: {len(missing)} employees")
                print("\nThese will be updated if Connecteam has their clock-out times.")
                return True
            else:
                print("\n✅ No missing clock-outs from previous days!")
                return False
                
        finally:
            cursor.close()
            conn.close()


def main():
    """Main function with menu"""
    reconciler = ConnecteamReconciliation()
    
    print("=" * 60)
    print("CONNECTEAM DATA RECONCILIATION")
    print("=" * 60)
    
    # Show current status
    has_issues = reconciler.show_current_status()
    
    print("\nOptions:")
    print("1. Quick sync (last 2 days)")
    print("2. Weekly sync (last 7 days)")
    print("3. Monthly sync (last 30 days)")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        reconciler.reconcile_last_n_days(2)
    elif choice == '2':
        reconciler.reconcile_last_n_days(7)
    elif choice == '3':
        reconciler.reconcile_last_n_days(30)
    elif choice == '4':
        print("Exiting...")
    else:
        print("Invalid option")
    
    # Show status again if we did a sync
    if choice in ['1', '2', '3']:
        print("\nFinal status:")
        reconciler.show_current_status()


if __name__ == "__main__":
    main()
