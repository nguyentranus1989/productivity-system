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

    # Query Dec 12, 2025 clock_times for the 3 confirmed employees
    query = """
    SELECT
        ct.id,
        e.name,
        ct.clock_in,
        ct.clock_out,
        ct.created_at
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE e.name IN ('Toan Chau', 'Man Nguyen', 'Andrea Romero')
    AND DATE(ct.clock_in) = '2025-12-12'
    ORDER BY e.name, ct.clock_in
    """

    cursor.execute(query)
    records = cursor.fetchall()

    # Timezone converters
    utc = pytz.UTC
    ct_tz = pytz.timezone('America/Chicago')

    # User-confirmed times (CT)
    confirmed = {
        'Toan Chau': {'expected': '4:45 AM', 'hour': 4, 'minute': 45},
        'Man Nguyen': {'expected': '2:06 AM', 'hour': 2, 'minute': 6},
        'Andrea Romero': {'expected': '5:09 AM', 'hour': 5, 'minute': 9}
    }

    print(f"\n{'='*120}")
    print(f"TIMEZONE DISCREPANCY ANALYSIS - December 12, 2025")
    print(f"{'='*120}\n")

    for name in ['Man Nguyen', 'Toan Chau', 'Andrea Romero']:
        print(f"\n{name}:")
        print(f"  User-confirmed clock-in: {confirmed[name]['expected']} CT")

        employee_records = [r for r in records if r['name'] == name]

        if not employee_records:
            print(f"  ❌ NO RECORDS FOUND IN DATABASE FOR DEC 12")
            continue

        print(f"  Database records found: {len(employee_records)}\n")

        for idx, record in enumerate(employee_records, 1):
            clock_in = record['clock_in']
            created_at = record['created_at']

            # Convert to CT
            if clock_in.tzinfo is None:
                clock_in_utc = utc.localize(clock_in)
            else:
                clock_in_utc = clock_in.astimezone(utc)
            clock_in_ct = clock_in_utc.astimezone(ct_tz)

            if created_at.tzinfo is None:
                created_at_utc = utc.localize(created_at)
            else:
                created_at_utc = created_at

            # Parse expected time
            expected_dt = ct_tz.localize(datetime(2025, 12, 12,
                                                  confirmed[name]['hour'],
                                                  confirmed[name]['minute']))

            # Calculate difference
            time_diff_minutes = (clock_in_ct - expected_dt).total_seconds() / 60
            time_diff_hours = time_diff_minutes / 60

            # Display
            print(f"  Record #{idx} (ID: {record['id']}):")
            print(f"    Clock-in (UTC):  {clock_in_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"    Clock-in (CT):   {clock_in_ct.strftime('%Y-%m-%d %I:%M:%S %p CT')}")
            print(f"    Created at:      {created_at_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"    Difference:      {time_diff_hours:+.2f} hours ({time_diff_minutes:+.0f} minutes)")

            if abs(time_diff_hours) > 0.1:
                print(f"    ** MISMATCH DETECTED!")
                if time_diff_hours > 0:
                    print(f"        DB shows {abs(time_diff_hours):.2f} hours LATER than expected")
                else:
                    print(f"        DB shows {abs(time_diff_hours):.2f} hours EARLIER than expected")
            else:
                print(f"    OK - MATCHES user-confirmed time")
            print()

    # Pattern analysis
    print(f"\n{'='*120}")
    print(f"PATTERN ANALYSIS")
    print(f"{'='*120}\n")

    # All Dec 12 records
    all_query = """
    SELECT
        ct.id,
        e.name,
        ct.clock_in,
        ct.created_at
    FROM clock_times ct
    JOIN employees e ON ct.employee_id = e.id
    WHERE DATE(ct.clock_in) = '2025-12-12'
    ORDER BY ct.created_at
    """

    cursor.execute(all_query)
    all_records = cursor.fetchall()

    # Group by created_at time ranges
    early_morning = []  # created before 3 AM CT
    morning = []        # created 3 AM - 12 PM CT
    afternoon = []      # created after 12 PM CT

    for record in all_records:
        if record['created_at']:
            created_at = record['created_at']
            if created_at.tzinfo is None:
                created_at_utc = utc.localize(created_at)
            else:
                created_at_utc = created_at
            created_at_ct = created_at_utc.astimezone(ct_tz)

            hour_ct = created_at_ct.hour

            if hour_ct < 3:
                early_morning.append(record['name'])
            elif hour_ct < 12:
                morning.append(record['name'])
            else:
                afternoon.append(record['name'])

    print(f"Records by sync time (created_at):")
    print(f"  Before 3 AM CT: {len(early_morning)} records")
    print(f"  3 AM - 12 PM CT: {len(morning)} records")
    print(f"  After 12 PM CT: {len(afternoon)} records")

    # Check if the 3 confirmed employees fall into specific pattern
    print(f"\nConfirmed employees sync time:")
    for name in ['Man Nguyen', 'Toan Chau', 'Andrea Romero']:
        employee_records = [r for r in records if r['name'] == name]
        if employee_records:
            created_at = employee_records[0]['created_at']
            if created_at.tzinfo is None:
                created_at_utc = utc.localize(created_at)
            else:
                created_at_utc = created_at
            created_at_ct = created_at_utc.astimezone(ct_tz)
            print(f"  {name}: {created_at_ct.strftime('%Y-%m-%d %I:%M:%S %p CT')}")

    print(f"\n{'='*120}\n")

finally:
    conn.close()
