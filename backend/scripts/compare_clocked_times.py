#!/usr/bin/env python3
"""
Compare clocked times: Database vs Frontend API

NOTE: clock_times stores UTC. MySQL NOW() returns UTC.
Both are in same timezone, so calculations are correct.

Run: cd backend && venv\\Scripts\\python.exe scripts\\compare_clocked_times.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pymysql
import requests
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

def compare():
    conn = get_connection()
    cursor = conn.cursor()

    ct_tz = pytz.timezone('America/Chicago')
    now_ct = datetime.now(ct_tz)

    print("=" * 90)
    print("CLOCKED TIME COMPARISON: Database vs Frontend API")
    print(f"Current CT Time: {now_ct.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

    # Get raw database data
    cursor.execute("""
        SELECT
            e.name,
            ct.clock_in,
            ct.clock_out,
            ct.total_minutes as db_total_minutes,
            CASE WHEN ct.clock_out IS NULL THEN 'ACTIVE' ELSE 'DONE' END as status,
            -- Calculate what frontend SHOULD show (with fix)
            TIMESTAMPDIFF(MINUTE, ct.clock_in,
                COALESCE(ct.clock_out, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))
            ) as calculated_minutes_fixed,
            -- Calculate what frontend WAS showing (broken)
            TIMESTAMPDIFF(MINUTE, ct.clock_in,
                COALESCE(ct.clock_out, NOW())
            ) as calculated_minutes_broken
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE DATE(ct.clock_in) = DATE(CONVERT_TZ(NOW(), '+00:00', 'America/Chicago'))
        ORDER BY ct.clock_in DESC
    """)

    db_data = cursor.fetchall()

    # Try to get frontend API data
    api_data = {}
    try:
        response = requests.get(
            'http://localhost:5000/api/dashboard/clock-times/today',
            headers={'X-API-Key': 'dev-api-key-123'},
            timeout=5
        )
        if response.ok:
            for item in response.json():
                api_data[item['employee_name']] = item['total_minutes']
    except Exception as e:
        print(f"Warning: Could not fetch API data: {e}")
        print("Make sure backend is running: venv\\Scripts\\python.exe app.py")
        print()

    print(f"\n{'Employee':<22} {'Clock In':<12} {'Status':<8} {'DB Min':<8} {'API Min':<8} {'Fixed':<8} {'Broken':<8} {'Issue'}")
    print("-" * 90)

    issues_found = 0
    for row in db_data:
        name = row['name'][:21]
        clock_in = row['clock_in'].strftime('%H:%M') if row['clock_in'] else '-'
        status = row['status']
        db_min = row['db_total_minutes'] or 0
        api_min = api_data.get(row['name'], '-')
        fixed_min = row['calculated_minutes_fixed']
        broken_min = row['calculated_minutes_broken']

        # Detect issues
        issue = ""
        if status == 'ACTIVE':
            if api_min != '-' and isinstance(api_min, int):
                if abs(api_min - fixed_min) > 30:
                    issue = "API WRONG!"
                    issues_found += 1
                elif abs(broken_min - fixed_min) > 60:
                    issue = "Was broken, now fixed"

        print(f"{name:<22} {clock_in:<12} {status:<8} {db_min:<8} {str(api_min):<8} {fixed_min:<8} {broken_min:<8} {issue}")

    print("-" * 90)
    print(f"Total records today: {len(db_data)}")
    print(f"Issues found: {issues_found}")

    if issues_found > 0:
        print("\n*** RESTART BACKEND to apply timezone fix! ***")
    elif api_data:
        print("\nAll times look correct!")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    compare()
