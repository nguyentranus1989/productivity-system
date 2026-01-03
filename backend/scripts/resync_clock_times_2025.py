#!/usr/bin/env python3
"""
Re-sync clock_times from Connecteam for full year 2025.
Can resume from a specific date if needed.
"""

import sys
import os
import time
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database.db_manager import get_db
from integrations.connecteam_sync import ConnecteamSync


def main():
    print("=" * 60)
    print("SYNC CLOCK TIMES - FULL YEAR 2025")
    print("=" * 60)
    print()

    db = get_db()

    # Check current state
    existing = db.fetch_one("""
        SELECT COUNT(*) as cnt, MAX(DATE(clock_in)) as latest
        FROM clock_times WHERE YEAR(clock_in) = 2025
    """)
    print(f"Current 2025 records: {existing['cnt']:,}")
    if existing['latest']:
        print(f"Latest synced date: {existing['latest']}")

    # Determine start date (resume from next day after latest)
    if existing['latest']:
        start_date = existing['latest'] + timedelta(days=1)
    else:
        start_date = date(2025, 1, 1)

    end_date = date(2025, 12, 31)

    if start_date > end_date:
        print("Already fully synced!")
        return

    total_days = (end_date - start_date).days + 1

    print()
    print(f"Will sync: {start_date} to {end_date} ({total_days} days)")
    print()

    config = Config()
    sync = ConnecteamSync(
        api_key=config.CONNECTEAM_API_KEY,
        clock_id=config.CONNECTEAM_CLOCK_ID
    )

    # Stats
    total_stats = {
        'days_processed': 0,
        'days_with_data': 0,
        'total_shifts': 0,
        'created': 0,
        'errors': 0
    }

    start_time = time.time()
    current_date = start_date

    while current_date <= end_date:
        day_num = (current_date - start_date).days + 1
        progress = (day_num / total_days) * 100

        print(f"[{day_num:3d}/{total_days}] {current_date} ({progress:5.1f}%) ... ", end="", flush=True)

        try:
            day_stats = sync.sync_shifts_for_date_v2(current_date)

            total_stats['days_processed'] += 1
            total_stats['total_shifts'] += day_stats.get('total_shifts', 0)
            total_stats['created'] += day_stats.get('created', 0)
            total_stats['errors'] += day_stats.get('errors', 0)

            if day_stats.get('total_shifts', 0) > 0:
                total_stats['days_with_data'] += 1
                print(f"OK {day_stats['total_shifts']} shifts")
            else:
                print("- no shifts")

            # Rate limiting
            time.sleep(0.3)

        except Exception as e:
            print(f"ERROR: {e}")
            total_stats['errors'] += 1
            time.sleep(1)

        current_date += timedelta(days=1)

    elapsed = time.time() - start_time

    # Final stats
    print()
    print("=" * 60)
    print("RE-SYNC COMPLETE")
    print("=" * 60)
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Days processed: {total_stats['days_processed']}")
    print(f"Days with data: {total_stats['days_with_data']}")
    print(f"Total shifts: {total_stats['total_shifts']}")
    print(f"Records created: {total_stats['created']}")
    print(f"Errors: {total_stats['errors']}")

    # Verify
    final = db.fetch_one("""
        SELECT
            COUNT(*) as total,
            MIN(DATE(clock_in)) as earliest,
            MAX(DATE(clock_in)) as latest
        FROM clock_times WHERE YEAR(clock_in) = 2025
    """)
    print()
    print(f"Final 2025 records: {final['total']:,}")
    print(f"Date range: {final['earliest']} to {final['latest']}")


if __name__ == "__main__":
    main()
