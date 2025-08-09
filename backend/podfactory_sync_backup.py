import pymysql
import mysql.connector
import requests
import json
from datetime import datetime, timedelta
import pytz
import time
import logging

# Map PodFactory actions to departments
ACTION_TO_DEPARTMENT_MAP = {
    'In Production': 'Heat Press',
    'Picking': 'Picking',
    'Labeling': 'Labeling',
    'Film Matching': 'Packing',
    'QC Passed': 'Packing'
}

# Map PodFactory user_role to our role_configs.id
PODFACTORY_ROLE_TO_CONFIG_ID = {
    'Heat Pressing': 1,
    'Packing and Shipping': 2,
    'Picker': 3,
    'Labeler': 4,
    'Film Matching': 5
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PodFactorySync:
    def __init__(self):
        # Database configurations
        self.local_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'Nicholasbin0116$',
            'database': 'productivity_tracker'
        }
        
        self.podfactory_config = {
            'host': 'db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
            'port': 25060,
            'user': 'doadmin',
            'password': 'AVNS_OWqdUdZ2Nw_YCkGI5Eu',
            'database': 'pod-report-stag',
            'ssl_disabled': False
        }
        
        # Your Flask API endpoint
        self.api_base = 'http://localhost:5000'
        
        # Timezone settings
        self.utc = pytz.UTC
        self.central = pytz.timezone('America/Chicago')
    
    def get_central_date(self):
        """Get current date in Central Time"""
        return datetime.now(self.central).date()
    
    def get_central_datetime(self):
        """Get current datetime in Central Time"""
        return datetime.now(self.central)
    
    def get_employee_mapping(self):
        """Get employee mappings using name-based matching"""
        conn = pymysql.connect(**self.local_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get all active employees
        cursor.execute("""
            SELECT 
                id as employee_id,
                name as display_name,
                LOWER(TRIM(name)) as normalized_name
            FROM employees
            WHERE is_active = 1
        """)
        
        employees = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Create comprehensive name mappings
        mappings = {}
        
        for emp in employees:
            employee_info = {
                'employee_id': emp['employee_id'],
                'name': emp['display_name']
            }
            
            # Store by normalized name
            normalized = emp['normalized_name']
            mappings[normalized] = employee_info
            
            # Also store common variations
            # "firstname lastname" -> "firstname.lastname"
            name_with_dot = normalized.replace(' ', '.')
            mappings[name_with_dot] = employee_info
            
            # "firstname lastname" -> "firstname_lastname"  
            name_with_underscore = normalized.replace(' ', '_')
            mappings[name_with_underscore] = employee_info
            
            # Just first name (for cases like "dung" instead of "dung duong")
            first_name = normalized.split(' ')[0]
            if first_name not in mappings:  # Only if not already taken
                mappings[first_name] = employee_info
            
            # NEW: Add last name only (for better matching)
            name_parts = normalized.split(' ')
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                # Only add last name if it's unique and longer than 3 chars
                if last_name not in mappings and len(last_name) > 3:
                    mappings[last_name] = employee_info
        
        # Manual mappings ONLY for truly special cases
        manual_mappings = {
            'vannesa apodaca': {'employee_id': 23, 'name': 'Vanessa Apodaca'},  # Misspelled
            'hau nguyen 2': {'employee_id': 20, 'name': 'Hau Nguyen'},  # Has "2" suffix
        }
        
        # Merge manual mappings
        mappings.update(manual_mappings)
        
        logger.info(f"Loaded {len(employees)} employees with {len(mappings)} name variations")
        return mappings 
    
    def extract_name_from_email(self, email):
        """Extract and normalize name from email address"""
        # Get the part before @
        email_prefix = email.split('@')[0].lower()
        
        # Remove common role suffixes
        suffixes_to_remove = ['shp', 'ship', 'pack', 'pick', 'label', 'film', 'heatpress', 'hp']
        for suffix in suffixes_to_remove:
            if email_prefix.endswith(suffix):
                email_prefix = email_prefix[:-len(suffix)]
                break
        
        # Return the cleaned prefix
        return email_prefix
    
    def find_employee_by_name(self, email, name_mappings, user_name=None):
        """Try to find employee using various name matching strategies"""
        # First, try to match using the actual user_name from PodFactory if provided
        if user_name:
            # Normalize the PodFactory name
            normalized_pf_name = user_name.lower().strip()
            
            # Try direct match
            if normalized_pf_name in name_mappings:
                return name_mappings[normalized_pf_name]
            
            # Try with common separators
            name_with_dot = normalized_pf_name.replace(' ', '.')
            if name_with_dot in name_mappings:
                return name_mappings[name_with_dot]
            
            name_with_underscore = normalized_pf_name.replace(' ', '_')
            if name_with_underscore in name_mappings:
                return name_mappings[name_with_underscore]
            
            # NEW: Try matching by parts - this handles "Michael Brown" matching "michael" or "brown"
            name_parts = normalized_pf_name.split()
            for part in name_parts:
                if len(part) > 3 and part in name_mappings:  # Skip short words
                    logger.debug(f"Matched '{user_name}' to employee via name part '{part}'")
                    return name_mappings[part]
            
            # NEW: Try fuzzy matching - look for any mapping that contains all significant parts
            significant_parts = [p for p in name_parts if len(p) > 2]  # Skip very short parts
            if significant_parts:
                for mapped_name, employee_info in name_mappings.items():
                    if all(part in mapped_name for part in significant_parts):
                        logger.debug(f"Fuzzy matched '{user_name}' to '{employee_info['name']}'")
                        return employee_info
        
        # Fall back to email-based matching
        email_name = self.extract_name_from_email(email)
        
        # Try direct match first
        if email_name in name_mappings:
            return name_mappings[email_name]
        
        # Try replacing common separators with space
        normalized_name = email_name.replace('.', ' ').replace('_', ' ')
        if normalized_name in name_mappings:
            return name_mappings[normalized_name]
        
        # Try replacing separators with other forms
        dot_form = email_name.replace('_', '.')
        if dot_form in name_mappings:
            return name_mappings[dot_form]
        
        underscore_form = email_name.replace('.', '_')
        if underscore_form in name_mappings:
            return name_mappings[underscore_form]
        
        # Try just the first part (for names like "anh_tu.le" -> "anh")
        first_part = email_name.split('.')[0].split('_')[0]
        if first_part in name_mappings:
            return name_mappings[first_part]
        
        return None
    
    def get_last_sync_time(self):
        """Get the last successful sync time"""
        conn = pymysql.connect(**self.local_config)
        cursor = conn.cursor()
        
        # Check if sync tracking table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS podfactory_sync_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                records_synced INT DEFAULT 0,
                status VARCHAR(50),
                notes TEXT
            )
        """)
        
        # Get last successful sync
        cursor.execute("""
            SELECT MAX(sync_time) as last_sync 
            FROM podfactory_sync_log 
            WHERE status IN ('SUCCESS', 'PARTIAL')
        """)
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0]:
            # Make sure it's timezone aware
            last_sync = result[0]
            if last_sync.tzinfo is None:
                # Assume database times are in Central
                last_sync = self.central.localize(last_sync)
            return last_sync
        else:
            # If no previous sync, start from beginning of today Central Time
            today = self.get_central_date()
            start_of_day = self.central.localize(datetime.combine(today, datetime.min.time()))
            return start_of_day
    
    def log_sync(self, records_synced, status, notes=""):
        """Log sync operation"""
        conn = pymysql.connect(**self.local_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO podfactory_sync_log (sync_time, records_synced, status, notes)
            VALUES (NOW(), %s, %s, %s)
        """, (records_synced, status, notes))
        
        conn.commit()
        cursor.close()
        conn.close()

    def get_sync_status_for_date(self, check_date):
        """Check if a specific date has been fully synced"""
        conn = pymysql.connect(**self.local_config)
        cursor = conn.cursor()
        
        # Check how much data we have for this date
        cursor.execute("""
            SELECT 
                COUNT(*) as record_count,
                MIN(TIME(window_start)) as earliest,
                MAX(TIME(window_start)) as latest,
                TIMESTAMPDIFF(HOUR, MIN(window_start), MAX(window_start)) as hours_covered
            FROM activity_logs
            WHERE DATE(window_start) = %s
            AND source = 'podfactory'
        """, (check_date,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0]:
            record_count = result[0]
            hours_covered = result[3] or 0
            
            # Consider it fully synced if:
            # 1. Has more than 100 records (typical day)
            # 2. Covers at least 6 hours of data
            return record_count > 100 and hours_covered >= 6
        
        return False

    def sync_missing_days(self, days_back=7):
        """Check and sync any missing days in the past X days"""
        logger.info(f"Checking for missing data in the last {days_back} days...")
        
        today = self.get_central_date()
        
        for days_ago in range(1, days_back + 1):
            check_date = today - timedelta(days=days_ago)
            
            if not self.get_sync_status_for_date(check_date):
                logger.warning(f"Date {check_date} is incomplete or missing. Syncing...")
                self.sync_date_range(check_date, check_date)
            else:
                logger.info(f"✓ Date {check_date} is fully synced")

    def fetch_new_activities(self, since_time):
        """Fetch activities from PodFactory since last sync"""
        conn = mysql.connector.connect(**self.podfactory_config)
        cursor = conn.cursor(dictionary=True)
        
        # Convert since_time to UTC for PodFactory query
        if since_time.tzinfo:
            since_utc = since_time.astimezone(self.utc)
        else:
            # Assume it's Central if no timezone
            since_central = self.central.localize(since_time)
            since_utc = since_central.astimezone(self.utc)
        
        # Also get a reasonable end time (now + 1 hour to catch any clock drift)
        end_utc = datetime.now(self.utc) + timedelta(hours=1)
        
        # FIXED: Use window_start for filtering, not created_at
        query = """
            SELECT 
                id,
                user_email,
                user_name,
                user_role,
                action,
                items_count,
                window_start,
                window_end,
                created_at
            FROM report_actions
            WHERE window_start > %s
            AND window_start <= %s
            AND items_count > 0
            ORDER BY window_start ASC
        """
        
        cursor.execute(query, (since_utc, end_utc))
        activities = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        logger.info(f"Fetched {len(activities)} activities with window_start after {since_time}")
        return activities
    
    def fetch_today_activities(self):
        """Fetch all activities for today in Central Time"""
        # Get today's date in Central Time
        today = self.get_central_date()
        start_of_day = self.central.localize(datetime.combine(today, datetime.min.time()))
        
        logger.info(f"Fetching all activities for {today} (Central Time)")
        return self.fetch_new_activities(start_of_day)
    
    def convert_to_central(self, utc_dt):
        """Convert UTC datetime to Central Time"""
        if utc_dt:
            if utc_dt.tzinfo is None:
                utc_dt = self.utc.localize(utc_dt)
            return utc_dt.astimezone(self.central)
        return None
    
    def send_to_api(self, activity_data):
        """Send activity to Flask API"""
        try:
            # First, try to create activity
            response = requests.post(
                f"{self.api_base}/api/dashboard/activities/activity",
                json=activity_data,
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': 'dev-api-key-123'
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'duplicate':
                    logger.debug(f"Activity already exists: {activity_data['metadata']['podfactory_id']}")
                else:
                    logger.debug(f"Activity created successfully: {result.get('activity_id')}")
                return True
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send to API: {e}")
            return False
        
    def send_activities_batch(self, activities_batch):
        """Send multiple activities to Flask API in one request"""
        if not activities_batch:
            return True
            
        try:
            bulk_endpoint = f"{self.api_base}/api/dashboard/activities/bulk"
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': 'dev-api-key-123'
            }
            
            response = requests.post(
                bulk_endpoint,
                json=activities_batch,
                headers=headers,
                timeout=120  # Longer timeout for bulk
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully sent batch of {len(activities_batch)} activities")
                return True
            else:
                logger.error(f"❌ Bulk API error: {response.status_code} - {response.text}")
                # Fall back to sending one by one
                success_count = 0
                for activity in activities_batch:
                    if self.send_to_api(activity):
                        success_count += 1
                logger.info(f"Sent {success_count}/{len(activities_batch)} activities individually")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"Failed to send batch: {e}")
            return False

    def sync_activities(self, use_last_sync=True):
        """Main sync function with name-based matching"""
        logger.info("="*60)
        logger.info("Starting PodFactory sync with name-based mapping...")
        logger.info(f"Current Central Time: {self.get_central_datetime()}")
        
        # Get name-based mappings
        name_mappings = self.get_employee_mapping()
        if not name_mappings:
            logger.error("No employee mappings found!")
            return 0, 0
        
        # Get sync start time
        if use_last_sync:
            last_sync = self.get_last_sync_time()
            logger.info(f"Last sync was at: {last_sync}")
            activities = self.fetch_new_activities(last_sync)
        else:
            # Sync all of today's activities
            activities = self.fetch_today_activities()
        
        if not activities:
            logger.info("No new activities to sync")
            self.log_sync(0, "SUCCESS", "No new activities")
            return 0, 0
        
        # Group activities by date for logging
        activities_by_date = {}
        for activity in activities:
            window_central = self.convert_to_central(activity['window_start'])
            date_key = window_central.date()
            if date_key not in activities_by_date:
                activities_by_date[date_key] = 0
            activities_by_date[date_key] += 1
        
        logger.info("Activities by date:")
        for date_key, count in sorted(activities_by_date.items()):
            logger.info(f"  {date_key}: {count} activities")
        
        # Process activities in batches
        success_count = 0
        error_count = 0
        skipped_count = 0
        skipped_emails = {}  # Track skipped emails to log summary
        
        batch_size = 50  # Process 50 at a time
        activities_batch = []
        employee_names_batch = []  # To track names for logging
        
        for activity in activities:
            # Try to find employee by name
            employee = self.find_employee_by_name(
                activity['user_email'], 
                name_mappings, 
                user_name=activity.get('user_name')
            )
            if 'shp@' in activity['user_email'] or 'ship@' in activity['user_email']:
                logger.info(f"DEBUG: Shipping email {activity['user_email']} with name '{activity.get('user_name')}' - Found: {employee is not None}")
            if not employee:
                email = activity['user_email']
                if email not in skipped_emails:
                    skipped_emails[email] = 0
                skipped_emails[email] += 1
                skipped_count += 1
                continue
            
            window_start = activity['window_start']  # Keep as UTC
            window_end = activity['window_end']      # Keep as UTC
            
            # Calculate duration in minutes
            duration = 0
            if window_start and window_end:
                duration = int((window_end - window_start).total_seconds() / 60)
            
            # Get role_id from user_role
            user_role = activity.get('user_role', '')
            role_id = PODFACTORY_ROLE_TO_CONFIG_ID.get(user_role, 3)  # Default to Picker if not found
            
            # Map action to department using the new mapping
            department = ACTION_TO_DEPARTMENT_MAP.get(activity['action'], 'Unknown')
            
            # Determine scan type based on role
            scan_type = 'batch_scan' if role_id in [3, 4, 5] else 'item_scan'
            
            # Convert times to Central for logging
            window_start_central = self.convert_to_central(window_start)
            
            # Prepare data for API
            api_data = {
                'employee_id': employee['employee_id'],
                'scan_type': scan_type,
                'quantity': activity['items_count'] or 1,
                'department': department,
                'timestamp': window_start.isoformat() if window_start else datetime.now(self.utc).isoformat(),
                'window_end': window_end.isoformat() if window_end else None,  # ADD THIS LINE
                'metadata': {
                    'source': 'podfactory',
                    'podfactory_id': str(activity['id']),
                    'action': activity['action'],
                    'user_role': user_role,
                    'duration_minutes': duration,
                    'role_id': role_id
                }
            }
            
            activities_batch.append(api_data)
            employee_names_batch.append({
                'name': employee['name'],
                'action': activity['action'],
                'items': activity['items_count'],
                'time': window_start_central.strftime('%I:%M %p CT')
            })
            
            # Send batch when it reaches the size limit
            if len(activities_batch) >= batch_size:
                if self.send_activities_batch(activities_batch):
                    success_count += len(activities_batch)
                    # Log successful activities
                    for emp in employee_names_batch:
                        logger.info(f"✅ Synced: {emp['name']} - {emp['action']} ({emp['items']} items) - {emp['time']}")
                else:
                    error_count += len(activities_batch)
                    for emp in employee_names_batch:
                        logger.error(f"❌ Failed: {emp['name']} - {emp['action']}")
                
                activities_batch = []
                employee_names_batch = []
                time.sleep(0.5)  # Small delay between batches
        
        # Send remaining activities
        if activities_batch:
            if self.send_activities_batch(activities_batch):
                success_count += len(activities_batch)
                # Log successful activities
                for emp in employee_names_batch:
                    logger.info(f"✅ Synced: {emp['name']} - {emp['action']} ({emp['items']} items) - {emp['time']}")
            else:
                error_count += len(activities_batch)
                for emp in employee_names_batch:
                    logger.error(f"❌ Failed: {emp['name']} - {emp['action']}")
        
        # Log skipped emails summary
        if skipped_emails:
            logger.warning("\nSkipped emails (no name mapping found):")
            for email, count in sorted(skipped_emails.items()):
                extracted_name = self.extract_name_from_email(email)
                logger.warning(f"  {email} ({count} activities) - extracted: '{extracted_name}'")
        
        # Log sync results
        status = "SUCCESS" if error_count == 0 else "PARTIAL"
        notes = f"Synced {success_count} activities, {error_count} errors, {skipped_count} skipped"
        self.log_sync(success_count, status, notes)
        
        logger.info("="*60)
        logger.info(f"Sync complete! ✅ Success: {success_count}, ❌ Errors: {error_count}, ⏭️ Skipped: {skipped_count}")
        logger.info("="*60)
        
        return success_count, error_count
    
    def test_connection(self):
        """Test connections to both databases and API"""
        print("\nTesting connections...")
        print("-"*40)
        
        # Test local database
        try:
            conn = pymysql.connect(**self.local_config)
            conn.close()
            print("✅ Local database connection OK")
        except Exception as e:
            print(f"❌ Local database error: {e}")
            return False
        
        # Test PodFactory database
        try:
            conn = mysql.connector.connect(**self.podfactory_config)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM report_actions WHERE created_at >= CURDATE()")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            print(f"✅ PodFactory database connection OK ({count} activities today)")
        except Exception as e:
            print(f"❌ PodFactory database error: {e}")
            return False
        
        # Test Flask API
        try:
            response = requests.get(
                f"{self.api_base}/health",
                timeout=5
            )
            if response.status_code == 200:
                print("✅ Flask API connection OK")
            else:
                print(f"⚠️ Flask API returned status {response.status_code}")
        except Exception as e:
            print(f"⚠️ Flask API not responding (will test during sync)")
        
        print("-"*40)
        return True
    
    def debug_name_mapping(self):
        """Debug utility to show name mappings"""
        print("\nName Mapping Debug Info")
        print("="*60)
        
        mappings = self.get_employee_mapping()
        
        # Group by employee to show all variations
        employees = {}
        for name_variant, info in mappings.items():
            emp_id = info['employee_id']
            if emp_id not in employees:
                employees[emp_id] = {
                    'name': info['name'],
                    'variants': []
                }
            employees[emp_id]['variants'].append(name_variant)
        
        # Display mappings
        for emp_id, data in sorted(employees.items()):
            print(f"\nEmployee ID {emp_id}: {data['name']}")
            print(f"  Name variants that will match:")
            for variant in sorted(data['variants']):
                print(f"    - {variant}")
        
        print("\n" + "="*60)
    
    def run_continuous_sync(self, interval_minutes=5):
        """Run sync continuously"""
        logger.info(f"Starting continuous sync every {interval_minutes} minutes")
        logger.info(f"Current time: {self.get_central_datetime()}")
        
        while True:
            try:
                # Run sync
                success, errors = self.sync_activities()
                
                # Calculate next sync time
                next_sync = self.get_central_datetime() + timedelta(minutes=interval_minutes)
                logger.info(f"\nNext sync at: {next_sync.strftime('%I:%M:%S %p')} Central Time")
                logger.info(f"Waiting {interval_minutes} minutes...\n")
                
                # Wait for next sync
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("\nSync stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                logger.info("Waiting 1 minute before retry...")
                time.sleep(60)
    
    def sync_date_range(self, start_date, end_date):
        """Sync activities for a specific date range"""
        logger.info(f"Syncing activities from {start_date} to {end_date}")
        
        # Convert dates to Central Time datetimes
        start_dt = self.central.localize(datetime.combine(start_date, datetime.min.time()))
        end_dt = self.central.localize(datetime.combine(end_date, datetime.max.time()))
        
        # Fetch activities directly for this date range
        conn = mysql.connector.connect(**self.podfactory_config)
        cursor = conn.cursor(dictionary=True)
        
        # Convert to UTC for query
        start_utc = start_dt.astimezone(self.utc)
        end_utc = end_dt.astimezone(self.utc)
        
        query = """
            SELECT 
                id,
                user_email,
                user_name,
                user_role,
                action,
                items_count,
                window_start,
                window_end,
                created_at
            FROM report_actions
            WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) >= %s
            AND DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) <= %s
            AND items_count > 0
            ORDER BY window_start ASC
        """
        
        cursor.execute(query, (start_date, end_date))
        activities = cursor.fetchall()
        cursor.close()
        conn.close()
        
        logger.info(f"Found {len(activities)} activities for {start_date} to {end_date}")
        
        if not activities:
            logger.info("No activities to sync for this date range")
            self.log_sync(0, "SUCCESS", f"No activities for {start_date} to {end_date}")
            return 0, 0
        
        # Temporarily set activities for processing
        # Save the original fetch method
        original_fetch = self.fetch_new_activities
        self.fetch_new_activities = lambda x: activities
        
        try:
            # Process using existing sync logic
            success, errors = self.sync_activities(use_last_sync=False)
        finally:
            # Restore original method
            self.fetch_new_activities = original_fetch
        
        return success, errors
# Main execution
if __name__ == "__main__":
    sync = PodFactorySync()
    
    # Test connections first
    if not sync.test_connection():
        print("\n❌ Fix connection issues before running sync")
        exit(1)
    
    print("\n" + "="*50)
    print("PodFactory Activity Sync (Name-Based Mapping)")
    print(f"Current Central Time: {sync.get_central_datetime().strftime('%Y-%m-%d %I:%M:%S %p')}")
    print("="*50)
    print("\nChoose sync mode:")
    print("1. Sync new activities (since last sync)")
    print("2. Sync all of today's activities") 
    print("3. Run continuous sync (every 5 minutes)")
    print("4. Sync specific date range")
    print("5. Test with last 1 hour of data")
    print("6. Debug name mappings")
    print("="*50)
    
    choice = input("\nEnter choice (1-6): ")
    
    if choice == "1":
        sync.sync_activities(use_last_sync=True)
    
    elif choice == "2":
        sync.sync_activities(use_last_sync=False)
    
    elif choice == "3":
        interval = input("Enter sync interval in minutes (default 5): ")
        interval = int(interval) if interval else 5
        sync.run_continuous_sync(interval_minutes=interval)
    
    elif choice == "4":
        print("\nEnter date range (YYYY-MM-DD format)")
        start_str = input("Start date: ")
        end_str = input("End date: ")
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            sync.sync_date_range(start_date, end_date)
        except ValueError:
            print("Invalid date format!")
    
    elif choice == "5":
        # Override last sync time for testing
        test_time = sync.get_central_datetime() - timedelta(hours=1)
        sync.get_last_sync_time = lambda: test_time
        sync.sync_activities(use_last_sync=True)
    
    elif choice == "6":
        sync.debug_name_mapping()
    
    else:
        print("Invalid choice!")
        
    print("\n✨ Done!")