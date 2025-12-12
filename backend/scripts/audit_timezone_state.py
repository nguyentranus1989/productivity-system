#!/usr/bin/env python3
"""
Audit script to verify timezone state of clock_times data.

CONCLUSION: clock_times stores UTC timestamps.
- Connecteam API returns Unix timestamps
- datetime.fromtimestamp() on production server (UTC) converts to UTC
- MySQL NOW() also returns UTC
- Both are in same timezone, so TIMESTAMPDIFF works correctly

Run: cd backend && venv\\Scripts\\python.exe scripts\\audit_timezone_state.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pymysql
from datetime import datetime
import pytz
from config import config

def get_connection():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def audit_timezone():
    conn = get_connection()
    cursor = conn.cursor()

    print("=" * 70)
    print("TIMEZONE AUDIT REPORT")
    print("=" * 70)

    # 1. Check MySQL server timezone
    print("\n1. MySQL Server Timezone Settings:")
    print("-" * 40)
    cursor.execute("SELECT @@global.time_zone as global_tz, @@session.time_zone as session_tz, NOW() as server_now, UTC_TIMESTAMP() as utc_now")
    tz_info = cursor.fetchone()
    print(f"   Global TZ:     {tz_info['global_tz']}")
    print(f"   Session TZ:    {tz_info['session_tz']}")
    print(f"   NOW():         {tz_info['server_now']}")
    print(f"   UTC_TIMESTAMP: {tz_info['utc_now']}")

    # Calculate offset
    now_dt = tz_info['server_now']
    utc_dt = tz_info['utc_now']
    offset_hours = (now_dt - utc_dt).total_seconds() / 3600
    print(f"   Offset:        {offset_hours:+.1f} hours from UTC")

    # 2. Check sample clock_times data
    print("\n2. Sample Clock Times Data (last 10 records):")
    print("-" * 40)
    cursor.execute("""
        SELECT
            ct.id,
            e.name,
            ct.clock_in,
            ct.clock_out,
            ct.total_minutes,
            CASE WHEN ct.clock_out IS NULL THEN 'ACTIVE' ELSE 'DONE' END as status
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        ORDER BY ct.clock_in DESC
        LIMIT 10
    """)
    samples = cursor.fetchall()

    for s in samples:
        print(f"   {s['name'][:15]:<15} | {s['clock_in']} -> {s['clock_out'] or 'ACTIVE':<19} | {s['total_minutes'] or 0:>5} min")

    # 3. Check currently clocked-in employees
    print("\n3. Currently Clocked In (clock_out IS NULL):")
    print("-" * 40)
    cursor.execute("""
        SELECT
            e.name,
            ct.clock_in,
            TIMESTAMPDIFF(MINUTE, ct.clock_in, NOW()) as minutes_if_now_utc,
            TIMESTAMPDIFF(MINUTE, ct.clock_in, CONVERT_TZ(NOW(), @@session.time_zone, 'America/Chicago')) as minutes_if_now_ct
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE ct.clock_out IS NULL
        AND DATE(ct.clock_in) = CURDATE()
        ORDER BY ct.clock_in
    """)
    active = cursor.fetchall()

    if active:
        ct_tz = pytz.timezone('America/Chicago')
        current_ct = datetime.now(ct_tz)
        print(f"   Current CT time: {current_ct.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        for a in active:
            clock_in_time = a['clock_in']
            # Calculate what minutes SHOULD be (assuming clock_in is CT)
            if hasattr(clock_in_time, 'hour'):
                expected_minutes = (current_ct.replace(tzinfo=None) - clock_in_time).total_seconds() / 60
            else:
                expected_minutes = "?"

            print(f"   {a['name'][:20]:<20}")
            print(f"      clock_in:           {a['clock_in']}")
            print(f"      TIMESTAMPDIFF(NOW): {a['minutes_if_now_utc']} min")
            print(f"      Expected (if CT):   {expected_minutes:.0f} min" if isinstance(expected_minutes, float) else f"      Expected: {expected_minutes}")

            # Check for mismatch
            if isinstance(expected_minutes, float) and a['minutes_if_now_utc']:
                diff = abs(a['minutes_if_now_utc'] - expected_minutes)
                if diff > 60:  # More than 1 hour difference
                    print(f"      *** MISMATCH: {diff:.0f} min difference! ***")
            print()
    else:
        print("   No employees currently clocked in today.")

    # 4. Check for timezone-related anomalies
    print("\n4. Data Quality Checks:")
    print("-" * 40)

    # Negative hours
    cursor.execute("""
        SELECT COUNT(*) as count FROM clock_times
        WHERE clock_out IS NOT NULL
        AND clock_out < clock_in
    """)
    neg = cursor.fetchone()
    print(f"   Records with clock_out < clock_in: {neg['count']}")

    # Extremely long shifts (>16 hours)
    cursor.execute("""
        SELECT COUNT(*) as count FROM clock_times
        WHERE total_minutes > 960
    """)
    long_shifts = cursor.fetchone()
    print(f"   Shifts > 16 hours: {long_shifts['count']}")

    # Today's data count
    cursor.execute("""
        SELECT COUNT(*) as count FROM clock_times
        WHERE DATE(clock_in) = CURDATE()
    """)
    today = cursor.fetchone()
    print(f"   Records for today (CURDATE): {today['count']}")

    # 5. Recommendation
    print("\n5. ANALYSIS:")
    print("-" * 40)

    if offset_hours == 0:
        print("   MySQL server is in UTC timezone.")
        print("   clock_times stores UTC (from datetime.fromtimestamp on UTC server).")
        print("   NOW() also returns UTC.")
        print("   -> Both are in UTC, so TIMESTAMPDIFF works correctly.")
    else:
        print(f"   MySQL server is {offset_hours:+.1f} hours from UTC.")
        print("   NOW() and clock_in should be in same timezone.")

    print("\n" + "=" * 70)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    audit_timezone()
