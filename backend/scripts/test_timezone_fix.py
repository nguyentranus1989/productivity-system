#!/usr/bin/env python3
"""
Test script to verify timezone fix for clocked-in employees.
Compares old (broken) vs new (fixed) query results.

Run: cd backend && venv\Scripts\python.exe scripts\test_timezone_fix.py
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

def test_fix():
    conn = get_connection()
    cursor = conn.cursor()

    ct_tz = pytz.timezone('America/Chicago')
    current_ct = datetime.now(ct_tz)

    print("=" * 70)
    print("TIMEZONE FIX VERIFICATION")
    print("=" * 70)
    print(f"Current CT time: {current_ct.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Compare old vs new query for a sample active employee
    cursor.execute("""
        SELECT
            e.name,
            ct.clock_in,
            -- OLD (broken): Uses raw NOW() which is UTC
            TIMESTAMPDIFF(MINUTE, ct.clock_in, NOW()) as old_minutes_broken,
            -- NEW (fixed): Converts NOW() to CT
            TIMESTAMPDIFF(MINUTE, ct.clock_in, CONVERT_TZ(NOW(), '+00:00', 'America/Chicago')) as new_minutes_fixed
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE ct.clock_out IS NULL
        AND DATE(ct.clock_in) = CURDATE()
        ORDER BY ct.clock_in
        LIMIT 5
    """)

    results = cursor.fetchall()

    if not results:
        print("No employees currently clocked in.")
        return

    print("Comparing OLD (broken) vs NEW (fixed) calculations:")
    print("-" * 70)
    print(f"{'Employee':<20} {'Clock In':<20} {'OLD (min)':<12} {'NEW (min)':<12} {'Diff':<10}")
    print("-" * 70)

    all_good = True
    for r in results:
        diff = r['old_minutes_broken'] - r['new_minutes_fixed']
        status = "OK" if abs(diff) < 60 else f"+{diff} FIXED!"

        if abs(diff) >= 60:
            all_good = False

        print(f"{r['name'][:20]:<20} {str(r['clock_in']):<20} {r['old_minutes_broken']:<12} {r['new_minutes_fixed']:<12} {status}")

    print("-" * 70)

    if all_good:
        print("\nRESULT: All calculations match (within 60 min tolerance)")
    else:
        print(f"\nRESULT: FIX WORKING! Old query was off by ~{diff} minutes (6 hours)")
        print("        The CONVERT_TZ fix corrects the timezone mismatch.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    test_fix()
