#!/usr/bin/env python3
"""
Continuous PodFactory Sync Service
"""
import time
import schedule
import logging
from podfactory_sync import PodFactorySync
import pymysql  # Add this import
from datetime import datetime, timedelta  # Make sure timedelta is imported

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/continuous_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_and_sync_gaps():
    """Check for gaps in the last 7 days and sync them"""
    logger.info("Checking for data gaps in the last 7 days...")
    
    try:
        sync = PodFactorySync()
        
        # Check last 7 days
        today = datetime.now().date()
        
        # List to store dates that need syncing
        dates_to_sync = []
        
        # FIRST: Check all dates and identify which need syncing
        logger.info("Analyzing last 7 days...")
        for days_ago in range(1, 4):  # Check 1-3 days ago
            check_date = today - timedelta(days=days_ago)
            
            # Use the sync object's config which we know works
            conn = pymysql.connect(**sync.local_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as count,
                    MIN(TIME(window_start)) as earliest,
                    MAX(TIME(window_start)) as latest,
                    TIMESTAMPDIFF(HOUR, MIN(window_start), MAX(window_start)) as hours_covered,
                    COUNT(DISTINCT employee_id) as employees_active
                FROM activity_logs
                WHERE DATE(window_start) = %s
                AND source = 'podfactory'
            """, (check_date,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            count = result[0] if result and result[0] else 0
            hours_covered = result[3] if result and result[3] else 0
            employees_active = result[4] if result and result[4] else 0
            
            # Determine if sync is needed - using OR logic
            needs_sync = False
            reason = ""
            
            if count == 0:
                needs_sync = True
                reason = "No data"
            elif count < 300:  # 300 threshold
                needs_sync = True
                reason = f"Only {count} records (expected 400+)"
            elif hours_covered < 6:  # Less than 6 hours of data
                needs_sync = True
                reason = f"Only {hours_covered} hours covered"
            elif employees_active < 10:  # Less than 10 employees
                needs_sync = True  
                reason = f"Only {employees_active} employees"
            
            # Add to sync list if needed
            if needs_sync:
                logger.warning(f"  {check_date}: NEEDS SYNC - {reason}")
                dates_to_sync.append(check_date)
            else:
                logger.info(f"  {check_date}: OK - {count} records, {hours_covered}h coverage, {employees_active} employees")
        
        # SECOND: Now sync all dates that need it
        if dates_to_sync:
            logger.info(f"\nFound {len(dates_to_sync)} days that need syncing: {dates_to_sync}")
            logger.info("Starting sync process...")
            
            for idx, sync_date in enumerate(sorted(dates_to_sync), 1):
                logger.info(f"\n[{idx}/{len(dates_to_sync)}] Syncing {sync_date}...")
                try:
                    success, errors = sync.sync_date_range(sync_date, sync_date)
                    logger.info(f"✅ Completed {sync_date}: {success} activities synced, {errors} errors")
                except Exception as e:
                    logger.error(f"❌ Failed to sync {sync_date}: {str(e)}")
            
            logger.info(f"\nGap sync complete! Processed {len(dates_to_sync)} days.")
        else:
            logger.info("\nNo gaps found - all days have sufficient data!")
                
    except Exception as e:
        logger.error(f"Error checking gaps: {str(e)}", exc_info=True)

def sync_today_activities():
    """Sync all of today's activities"""
    try:
        logger.info("Starting PodFactory sync for today's activities...")
        
        # Initialize sync
        sync = PodFactorySync()
        
        # Get today's date as a date object, not string
        today = datetime.now().date()
        
        # Sync today's activities
        sync.sync_date_range(today, today)
        
        logger.info("PodFactory sync completed successfully")
        
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}", exc_info=True)

def sync_recent_activities():
    """Sync only recent activities (last 30 minutes)"""
    try:
        logger.info("Starting PodFactory sync for recent activities...")
        
        # Initialize sync
        sync = PodFactorySync()
        
        # Use option 1 (sync since last sync)
        sync.sync_activities(use_last_sync=True)
        
        logger.info("Recent activities sync completed successfully")
        
    except Exception as e:
        logger.error(f"Error during recent sync: {str(e)}", exc_info=True)

def main():
    logger.info("Starting Continuous PodFactory Sync Service")
    
    # CHECK FOR GAPS FIRST!
    check_and_sync_gaps()

    # Then do today's sync
    sync_today_activities()
    
    # Schedule regular syncs
    schedule.every(2).minutes.do(sync_recent_activities)  # Quick sync every 2 min
    schedule.every().day.at("00:01").do(sync_today_activities)  # Full sync at midnight
    schedule.every().day.at("06:00").do(sync_today_activities)  # Full sync at 6 AM
    schedule.every().day.at("12:00").do(sync_today_activities)  # Full sync at noon
    schedule.every().day.at("20:00").do(sync_today_activities)  # Full sync at 8 PM - catches end of day

    logger.info("Sync schedule configured:")
    logger.info("- Recent activities: Every 2 minutes")
    logger.info("- Full daily sync: Midnight, 6 AM, Noon and 8 PM")
    
    # Keep running
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            logger.info("Sync service stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main()