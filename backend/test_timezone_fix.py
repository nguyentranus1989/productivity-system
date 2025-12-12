"""Test timezone fix for clock_in display"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from database.db_manager import DatabaseManager
db = DatabaseManager()

# Test: Get Duc Nguyen clock-in time with the fixed query (no CONVERT_TZ on clock_in)
result = db.execute_query("""
    SELECT
        e.name,
        DATE_FORMAT(ct.clock_in, '%h:%i %p') as clock_in_display,
        ct.clock_in as raw_clock_in,
        DATE(ct.clock_in) as clock_date,
        DATE(CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', 'America/Chicago')) as today_central
    FROM employees e
    LEFT JOIN clock_times ct ON e.id = ct.employee_id
    WHERE e.name = 'Duc Nguyen'
    AND DATE(ct.clock_in) = DATE(CONVERT_TZ(UTC_TIMESTAMP(), '+00:00', 'America/Chicago'))
    ORDER BY ct.clock_in DESC
    LIMIT 1
""")

print('=== Timezone Fix Test ===')
if result:
    r = result[0]
    print(f'Employee: {r["name"]}')
    print(f'Clock-in Display: {r["clock_in_display"]}')
    print(f'Raw Clock-in: {r["raw_clock_in"]}')
    print(f'Clock Date: {r["clock_date"]}')
    print(f'Today Central: {r["today_central"]}')

    # Verify the time is correct (should be around 6:07 AM, not 12:07 AM)
    hour = r["raw_clock_in"].hour
    if hour >= 5 and hour <= 8:
        print('\n✓ SUCCESS: Clock-in time shows correct morning time!')
    else:
        print(f'\n✗ WARNING: Hour is {hour}, expected 5-8 for morning shift')
else:
    print('No clock-in record found for today')
