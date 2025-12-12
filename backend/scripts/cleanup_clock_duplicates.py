#!/usr/bin/env python3
"""
Cleanup script for clock_times duplicates and invalid records.

Issues found:
1. Records with negative total_minutes (clock_out < clock_in due to timezone bug)
2. Duplicate records created with 6-hour offset (UTC vs CT confusion)
3. Phantom active records that should be completed

Run: cd backend && venv\\Scripts\\python.exe scripts\\cleanup_clock_duplicates.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pymysql
from datetime import datetime, timedelta
import pytz
from config import config

def get_connection():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

def cleanup():
    conn = get_connection()
    cursor = conn.cursor()

    ct_tz = pytz.timezone('America/Chicago')
    today_ct = datetime.now(ct_tz).strftime('%Y-%m-%d')

    print("=" * 70)
    print("CLOCK_TIMES CLEANUP SCRIPT")
    print("=" * 70)
    print()

    stats = {
        'negative_fixed': 0,
        'duplicates_removed': 0,
        'phantoms_removed': 0
    }

    # Step 1: Fix records with negative total_minutes (clock_out < clock_in)
    # These have clock_out stored in wrong timezone - delete them as duplicates
    print("Step 1: Removing records with clock_out < clock_in (timezone bug)...")

    cursor.execute("""
        SELECT id, employee_id, clock_in, clock_out, total_minutes
        FROM clock_times
        WHERE clock_out IS NOT NULL AND clock_out < clock_in
    """)
    bad_records = cursor.fetchall()

    for r in bad_records:
        # Check if there's a correct record for same employee/day
        cursor.execute("""
            SELECT id FROM clock_times
            WHERE employee_id = %s
            AND DATE(clock_in) = DATE(%s)
            AND id != %s
            AND (clock_out IS NULL OR clock_out > clock_in)
        """, (r['employee_id'], r['clock_in'], r['id']))

        if cursor.fetchone():
            # Delete the bad record - there's a good one
            cursor.execute("DELETE FROM clock_times WHERE id = %s", (r['id'],))
            stats['negative_fixed'] += 1
            print(f"  Deleted bad record ID {r['id']} (negative minutes: {r['total_minutes']})")

    print(f"  Fixed: {stats['negative_fixed']} records")
    print()

    # Step 2: Remove timezone-shifted duplicates (6-hour offset)
    print("Step 2: Removing timezone-shifted duplicates...")

    cursor.execute("""
        SELECT
            ct1.id as dup_id,
            ct1.employee_id,
            ct1.clock_in as dup_clock_in,
            ct2.id as keep_id,
            ct2.clock_in as keep_clock_in,
            TIMESTAMPDIFF(HOUR, ct1.clock_in, ct2.clock_in) as hour_diff
        FROM clock_times ct1
        JOIN clock_times ct2 ON ct1.employee_id = ct2.employee_id
            AND ct1.id > ct2.id
            AND DATE(CONVERT_TZ(ct1.clock_in, '+00:00', 'America/Chicago')) =
                DATE(CONVERT_TZ(ct2.clock_in, '+00:00', 'America/Chicago'))
            AND ABS(TIMESTAMPDIFF(HOUR, ct1.clock_in, ct2.clock_in)) = 6
        WHERE ct1.clock_out IS NOT NULL OR ct2.clock_out IS NOT NULL
    """)

    dup_pairs = cursor.fetchall()
    deleted_ids = set()

    for pair in dup_pairs:
        if pair['dup_id'] in deleted_ids:
            continue

        # Keep the record with valid clock_out, delete the other
        cursor.execute("SELECT clock_out, total_minutes FROM clock_times WHERE id = %s", (pair['keep_id'],))
        keep = cursor.fetchone()

        cursor.execute("SELECT clock_out, total_minutes FROM clock_times WHERE id = %s", (pair['dup_id'],))
        dup = cursor.fetchone()

        # Keep the one with positive total_minutes or valid clock_out
        if keep and keep['total_minutes'] and keep['total_minutes'] > 0:
            cursor.execute("DELETE FROM clock_times WHERE id = %s", (pair['dup_id'],))
            deleted_ids.add(pair['dup_id'])
            stats['duplicates_removed'] += 1
        elif dup and dup['total_minutes'] and dup['total_minutes'] > 0:
            cursor.execute("DELETE FROM clock_times WHERE id = %s", (pair['keep_id'],))
            deleted_ids.add(pair['keep_id'])
            stats['duplicates_removed'] += 1

    print(f"  Removed: {stats['duplicates_removed']} duplicate records")
    print()

    # Step 3: Mark phantom active records as inactive if Connecteam shows completed
    # (Can't automatically fix without Connecteam API data, so just report)
    print("Step 3: Checking for phantom active records...")

    cursor.execute("""
        SELECT ct.id, e.name, ct.clock_in, ct.clock_out
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE ct.is_active = 1
        AND ct.clock_out IS NULL
        AND DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) < %s
    """, (today_ct,))

    old_active = cursor.fetchall()
    if old_active:
        print("  WARNING: Found active records from before today:")
        for r in old_active:
            print(f"    ID {r['id']} | {r['name']} | clock_in: {r['clock_in']}")
        print("  These should be reviewed manually or synced from Connecteam.")
    else:
        print("  No stale active records found.")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Records with clock_out < clock_in fixed: {stats['negative_fixed']}")
    print(f"  Timezone-shifted duplicates removed: {stats['duplicates_removed']}")
    print(f"  Total records cleaned: {stats['negative_fixed'] + stats['duplicates_removed']}")
    print()

    # Confirm before commit
    if '--commit' in sys.argv:
        conn.commit()
        print("Changes committed.")
    else:
        conn.rollback()
        print("DRY RUN - Changes rolled back. Use --commit to apply.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    cleanup()
