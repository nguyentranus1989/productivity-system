# daily_reconciliation.py
"""
Daily reconciliation job to recheck last 7 days of Connecteam data
Catches missed clock-outs, retroactive approvals, and data corrections
Run this once daily at night (e.g., 11 PM)
"""

import requests
from datetime import datetime, timedelta
import pytz
import logging
from typing import Dict, List, Optional
import mysql.connector

class ConnecteamReconciliation:
    def __init__(self, config):
        self.api_key = config['CONNECTEAM_API_KEY']
        self.clock_id = config['CONNECTEAM_CLOCK_ID']
        self.db_config = config['DB_CONFIG']
        self.central_tz = pytz.timezone('America/Chicago')
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def get_db_connection(self):
        """Get database connection"""
        return mysql.connector.connect(**self.db_config)
    
    def fetch_connecteam_data(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Fetch clock data from Connecteam for date range"""
        url = f"https://api.connecteam.com/v1/clocks/{self.clock_id}/entries"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'from': start_date.isoformat(),
            'to': end_date.isoformat(),
            'limit': 1000  # Get all entries
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('entries', [])
        except Exception as e:
            self.logger.error(f"Error fetching Connecteam data: {e}")
            return []
    
    def reconcile_last_7_days(self):
        """Main reconciliation function - checks last 7 days"""
        self.logger.info("Starting 7-day reconciliation sync...")
        
        # Get date range (last 7 days in Central Time)
        end_date = datetime.now(self.central_tz)
        start_date = end_date - timedelta(days=7)
        
        # Fetch data from Connecteam
        connecteam_entries = self.fetch_connecteam_data(start_date, end_date)
        self.logger.info(f"Fetched {len(connecteam_entries)} entries from Connecteam")
        
        # Process each entry
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        stats = {
            'updated': 0,
            'added': 0,
            'fixed_clock_outs': 0,
            'duplicates_removed': 0
        }
        
        try:
            for entry in connecteam_entries:
                employee_id = self.get_employee_id(cursor, entry['user_id'])
                if not employee_id:
                    continue
                
                clock_in = self.parse_datetime(entry['clock_in'])
                clock_out = self.parse_datetime(entry.get('clock_out'))
                
                # Check if record exists
                cursor.execute("""
                    SELECT id, clock_out 
                    FROM clock_times 
                    WHERE employee_id = %s 
                    AND DATE(clock_in) = DATE(%s)
                    AND TIME(clock_in) = TIME(%s)
                """, (employee_id, clock_in, clock_in))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update if clock_out was missing or changed
                    if existing['clock_out'] is None and clock_out:
                        cursor.execute("""
                            UPDATE clock_times 
                            SET clock_out = %s,
                                total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, %s),
                                updated_at = NOW()
                            WHERE id = %s
                        """, (clock_out, clock_out, existing['id']))
                        stats['fixed_clock_outs'] += 1
                        self.logger.info(f"Fixed missing clock-out for employee {employee_id}")
                    
                    elif existing['clock_out'] != clock_out:
                        cursor.execute("""
                            UPDATE clock_times 
                            SET clock_out = %s,
                                total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, %s),
                                updated_at = NOW()
                            WHERE id = %s
                        """, (clock_out, clock_out, existing['id']))
                        stats['updated'] += 1
                else:
                    # Add new record (retroactive approval case)
                    total_minutes = None
                    if clock_out:
                        total_minutes = int((clock_out - clock_in).total_seconds() / 60)
                    
                    cursor.execute("""
                        INSERT INTO clock_times 
                        (employee_id, clock_in, clock_out, total_minutes, 
                         is_active, source, connecteam_id, created_at)
                        VALUES (%s, %s, %s, %s, %s, 'connecteam', %s, NOW())
                    """, (
                        employee_id, clock_in, clock_out, total_minutes,
                        1 if not clock_out else 0, entry.get('id')
                    ))
                    stats['added'] += 1
                    self.logger.info(f"Added retroactive entry for employee {employee_id}")
            
            # Clean up duplicates
            stats['duplicates_removed'] = self.remove_duplicates(cursor)
            
            # Commit changes
            conn.commit()
            
            # Log summary
            self.logger.info(f"""
                Reconciliation Complete:
                - Fixed missing clock-outs: {stats['fixed_clock_outs']}
                - Updated entries: {stats['updated']}
                - Added retroactive entries: {stats['added']}
                - Duplicates removed: {stats['duplicates_removed']}
            """)
            
            # Update sync log
            cursor.execute("""
                INSERT INTO connecteam_sync_log 
                (started_at, status, records_synced, details)
                VALUES (NOW(), 'success', %s, %s)
            """, (
                sum(stats.values()),
                f"7-day reconciliation: {stats}"
            ))
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Error during reconciliation: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    def remove_duplicates(self, cursor) -> int:
        """Remove duplicate clock entries"""
        # Find and remove duplicates, keeping the one with clock_out
        cursor.execute("""
            DELETE ct1 FROM clock_times ct1
            INNER JOIN clock_times ct2
            WHERE ct1.id < ct2.id
            AND ct1.employee_id = ct2.employee_id
            AND DATE(ct1.clock_in) = DATE(ct2.clock_in)
            AND TIME(ct1.clock_in) = TIME(ct2.clock_in)
            AND (ct1.clock_out IS NULL OR ct2.clock_out IS NOT NULL)
        """)
        
        return cursor.rowcount
    
    def get_employee_id(self, cursor, connecteam_user_id: str) -> Optional[int]:
        """Get employee ID from Connecteam user ID"""
        cursor.execute("""
            SELECT id FROM employees 
            WHERE connecteam_user_id = %s
        """, (connecteam_user_id,))
        
        result = cursor.fetchone()
        return result['id'] if result else None
    
    def parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Connecteam"""
        if not dt_string:
            return None
        try:
            # Connecteam returns ISO format
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            # Convert to Central Time
            return dt.astimezone(self.central_tz)
        except:
            return None
    
    def fix_current_missing_clockouts(self):
        """Immediately fix the 7 employees with missing clock-outs"""
        conn = self.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get the problem records
            cursor.execute("""
                SELECT ct.id, ct.employee_id, ct.clock_in, e.name, e.connecteam_user_id
                FROM clock_times ct
                JOIN employees e ON ct.employee_id = e.id
                WHERE ct.clock_out IS NULL 
                AND DATE(ct.clock_in) < CURDATE()
                ORDER BY ct.clock_in
            """)
            
            missing_clockouts = cursor.fetchall()
            self.logger.info(f"Found {len(missing_clockouts)} missing clock-outs to fix")
            
            for record in missing_clockouts:
                # Fetch the correct data from Connecteam for this specific day
                clock_in_date = record['clock_in']
                start = clock_in_date.replace(hour=0, minute=0, second=0)
                end = clock_in_date.replace(hour=23, minute=59, second=59)
                
                entries = self.fetch_connecteam_data(start, end)
                
                # Find matching entry
                for entry in entries:
                    if entry['user_id'] == record['connecteam_user_id']:
                        entry_clock_in = self.parse_datetime(entry['clock_in'])
                        
                        # Check if times match (within 5 minutes)
                        time_diff = abs((entry_clock_in - clock_in_date).total_seconds())
                        if time_diff < 300:  # 5 minutes tolerance
                            clock_out = self.parse_datetime(entry.get('clock_out'))
                            if clock_out:
                                cursor.execute("""
                                    UPDATE clock_times 
                                    SET clock_out = %s,
                                        total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, %s),
                                        updated_at = NOW()
                                    WHERE id = %s
                                """, (clock_out, clock_out, record['id']))
                                
                                self.logger.info(f"Fixed clock-out for {record['name']} on {clock_in_date.date()}")
                                break
            
            conn.commit()
            self.logger.info("Immediate fix complete!")
            
        except Exception as e:
            self.logger.error(f"Error fixing clock-outs: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()


# Add to your scheduler.py
def schedule_reconciliation():
    """Add this to your scheduler to run daily at 11 PM"""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    
    scheduler = BackgroundScheduler(timezone='America/Chicago')
    
    config = {
        'CONNECTEAM_API_KEY': '9255ce96-70eb-4982-82ef-fc35a7651428',
        'CONNECTEAM_CLOCK_ID': 7425182,
        'DB_CONFIG': {
            'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
            'port': 25060,
            'user': 'doadmin',
            'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
            'database': 'productivity_tracker'
        }
    }
    
    reconciler = ConnecteamReconciliation(config)
    
    # Schedule daily reconciliation at 11 PM
    scheduler.add_job(
        func=reconciler.reconcile_last_7_days,
        trigger=CronTrigger(hour=23, minute=0),
        id='daily_reconciliation',
        name='Daily 7-day Connecteam reconciliation',
        replace_existing=True
    )
    
    scheduler.start()
    print("Daily reconciliation scheduled for 11 PM every day")


# Manual run script
if __name__ == "__main__":
    config = {
        'CONNECTEAM_API_KEY': '9255ce96-70eb-4982-82ef-fc35a7651428',
        'CONNECTEAM_CLOCK_ID': 7425182,
        'DB_CONFIG': {
            'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
            'port': 25060,
            'user': 'doadmin',
            'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
            'database': 'productivity_tracker'
        }
    }
    
    reconciler = ConnecteamReconciliation(config)
    
    # Fix immediate issues first
    print("Fixing current missing clock-outs...")
    reconciler.fix_current_missing_clockouts()
    
    # Then run full 7-day reconciliation
    print("\nRunning full 7-day reconciliation...")
    reconciler.reconcile_last_7_days()
