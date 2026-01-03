#!/usr/bin/env python3
"""
Recalculate daily_scores for all of 2025 after clock_times sync.
Run this AFTER resync_clock_times_2025.py completes.
"""

import sys
import os
from datetime import date, timedelta
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.productivity_calculator import ProductivityCalculator
from database.db_manager import get_db


def main():
    print("=" * 60)
    print("RECALCULATE DAILY SCORES - FULL YEAR 2025")
    print("=" * 60)
    print()

    db = get_db()
    calc = ProductivityCalculator()

    # DELETE all 2025 daily_scores first for clean slate
    print("Deleting all 2025 daily_scores...")
    db.execute_query("DELETE FROM daily_scores WHERE YEAR(score_date) = 2025")
    print("Deleted. Now recalculating...")
    print()

    # Get ALL dates with clock_times
    dates_with_data = db.fetch_all("""
        SELECT DISTINCT DATE(clock_in) as work_date
        FROM clock_times
        WHERE YEAR(clock_in) = 2025
        ORDER BY work_date
    """)

    total_days = len(dates_with_data)
    print(f"Found {total_days} days to calculate")
    print()

    if total_days == 0:
        print("No data to process!")
        return

    stats = {
        'days_processed': 0,
        'employees_processed': 0,
        'errors': 0
    }

    start_time = time.time()

    for i, row in enumerate(dates_with_data):
        work_date = row['work_date']
        progress = ((i + 1) / total_days) * 100

        import sys
        print(f"[{i+1:3d}/{total_days}] {work_date} ({progress:5.1f}%) ... ", end="")
        sys.stdout.flush()

        try:
            result = calc.process_all_employees_for_date(work_date)
            processed = result.get('processed', 0)
            stats['employees_processed'] += processed
            stats['days_processed'] += 1
            print(f"OK {processed} employees")

        except Exception as e:
            print(f"ERROR: {e}")
            stats['errors'] += 1

    elapsed = time.time() - start_time

    print()
    print("=" * 60)
    print("RECALCULATION COMPLETE")
    print("=" * 60)
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Days processed: {stats['days_processed']}")
    print(f"Employee-days: {stats['employees_processed']}")
    print(f"Errors: {stats['errors']}")

    # Verify
    final = db.fetch_one("""
        SELECT COUNT(*) as total, MIN(score_date) as earliest, MAX(score_date) as latest
        FROM daily_scores WHERE YEAR(score_date) = 2025
    """)
    print()
    print(f"Daily scores for 2025: {final['total']:,} records")
    print(f"Date range: {final['earliest']} to {final['latest']}")


if __name__ == "__main__":
    main()
