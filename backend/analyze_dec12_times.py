import pymysql
from dotenv import load_dotenv
from datetime import datetime
import pytz
import sys
import os

# Load environment
load_dotenv('C:/Users/12104/Projects/Productivity_system/backend/.env')
sys.path.insert(0, 'C:/Users/12104/Projects/Productivity_system/backend')
from config import config

# Connect to database
conn = pymysql.connect(
    host=config.DB_HOST,
    port=config.DB_PORT,
    user=config.DB_USER,
    password=config.DB_PASSWORD,
    database=config.DB_NAME,
    cursorclass=pymysql.cursors.DictCursor
)

try:
    cursor = conn.cursor()

    # Query all clock_times for Dec 12, 2025
    query = """
    SELECT
        ct.id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        ct.created_at
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE DATE(ct.clock_in) = '2025-12-12' OR DATE(ct.created_at) = '2025-12-12'
    ORDER BY ct.clock_in, ct.created_at
    """

    cursor.execute(query)
    records = cursor.fetchall()

    print(f"\n{'='*120}")
    print(f"CLOCK_TIMES ANALYSIS FOR DECEMBER 12, 2025")
    print(f"{'='*120}\n")
    print(f"Total records found: {len(records)}\n")

    # Timezone converters
    utc = pytz.UTC
    ct_tz = pytz.timezone('America/Chicago')

    # User-confirmed times (CT)
    confirmed = {
        'Toan Chau': '4:45 AM',
        'Man Nguyen': '2:06 AM',
        'Andrea Romero': '5:09 AM'
    }

    print(f"{'ID':<6} {'Name':<25} {'Clock-in UTC':<20} {'Clock-in CT':<20} {'Created_at':<20} {'Delta (hrs)':<12}")
    print(f"{'-'*120}")

    issues = []

    for record in records:
        clock_in = record['clock_in']
        created_at = record['created_at']
        name = record['name']

        # Convert to CT
        if clock_in:
            if clock_in.tzinfo is None:
                clock_in_utc = utc.localize(clock_in)
            else:
                clock_in_utc = clock_in.astimezone(utc)
            clock_in_ct = clock_in_utc.astimezone(ct_tz)
            clock_in_ct_str = clock_in_ct.strftime('%Y-%m-%d %I:%M:%S %p')
            clock_in_utc_str = clock_in_utc.strftime('%Y-%m-%d %H:%M:%S')
        else:
            clock_in_ct_str = 'NULL'
            clock_in_utc_str = 'NULL'
            clock_in_ct = None

        if created_at:
            if created_at.tzinfo is None:
                created_at_utc = utc.localize(created_at)
            else:
                created_at_utc = created_at
            created_at_str = created_at_utc.strftime('%Y-%m-%d %H:%M:%S')
        else:
            created_at_str = 'NULL'

        # Calculate time delta between created_at and clock_in
        delta_str = ''
        if clock_in and created_at:
            delta = (created_at_utc - clock_in_utc).total_seconds() / 3600
            delta_str = f"{delta:+.2f}h"

        print(f"{record['id']:<6} {name:<25} {clock_in_utc_str:<20} {clock_in_ct_str:<20} {created_at_str:<20} {delta_str:<12}")

        # Check against confirmed times
        if name in confirmed and clock_in_ct:
            expected_time = confirmed[name]
            actual_time = clock_in_ct.strftime('%I:%M %p').lstrip('0')

            # Parse expected time to compare
            from datetime import datetime
            expected_dt = datetime.strptime(f"2025-12-12 {expected_time}", "%Y-%m-%d %I:%M %p")
            expected_dt_ct = ct_tz.localize(expected_dt)

            time_diff = (clock_in_ct - expected_dt_ct).total_seconds() / 3600

            if abs(time_diff) > 0.1:  # More than 6 minutes off
                issues.append({
                    'name': name,
                    'expected': expected_time,
                    'actual_db': actual_time,
                    'diff_hours': time_diff,
                    'created_at': created_at_str,
                    'id': record['id']
                })

    # Summary of issues
    if issues:
        print(f"\n{'='*120}")
        print(f"DISCREPANCIES FOUND (User-Confirmed vs Database)")
        print(f"{'='*120}\n")

        for issue in issues:
            print(f"Employee: {issue['name']}")
            print(f"  ID: {issue['id']}")
            print(f"  Expected (user-confirmed): {issue['expected']} CT")
            print(f"  Database shows: {issue['actual_db']} CT")
            print(f"  Difference: {issue['diff_hours']:+.2f} hours ({issue['diff_hours']*60:+.1f} minutes)")
            print(f"  Created at: {issue['created_at']}")
            print()
    else:
        print(f"\n{'='*120}")
        print(f"NO DISCREPANCIES - All user-confirmed times match database")
        print(f"{'='*120}\n")

    # Pattern analysis
    print(f"\n{'='*120}")
    print(f"PATTERN ANALYSIS")
    print(f"{'='*120}\n")

    # Group by created_at hour
    early_sync = []  # created within 1 hour of clock_in
    late_sync = []   # created more than 1 hour after clock_in

    for record in records:
        if record['clock_in'] and record['created_at']:
            clock_in = record['clock_in']
            created_at = record['created_at']

            if clock_in.tzinfo is None:
                clock_in = utc.localize(clock_in)
            if created_at.tzinfo is None:
                created_at = utc.localize(created_at)

            delta_hours = (created_at - clock_in).total_seconds() / 3600

            if delta_hours <= 1:
                early_sync.append((record['name'], delta_hours))
            else:
                late_sync.append((record['name'], delta_hours))

    print(f"Records synced within 1 hour of clock-in: {len(early_sync)}")
    for name, delta in early_sync:
        print(f"  - {name}: {delta:.2f}h after clock-in")

    print(f"\nRecords synced >1 hour after clock-in: {len(late_sync)}")
    for name, delta in late_sync:
        print(f"  - {name}: {delta:.2f}h after clock-in")

    print(f"\n{'='*120}\n")

finally:
    conn.close()
