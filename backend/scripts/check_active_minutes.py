#!/usr/bin/env python3
"""Check and fix active_minutes in daily_scores."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pymysql
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

def check_and_fix():
    conn = get_connection()
    cursor = conn.cursor()

    today = "2025-12-11"

    print("=" * 100)
    print("CHECKING active_minutes in daily_scores vs activity_logs")
    print("=" * 100)

    # Get employees with their daily_scores and actual activity_logs duration
    cursor.execute("""
        SELECT
            e.id as employee_id,
            e.name,
            ds.clocked_minutes as ds_clocked,
            ds.active_minutes as ds_active,
            ds.items_processed as ds_items,
            COALESCE(al_sum.total_duration, 0) as actual_active
        FROM daily_scores ds
        JOIN employees e ON e.id = ds.employee_id
        LEFT JOIN (
            SELECT employee_id, SUM(duration_minutes) as total_duration
            FROM activity_logs
            WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = %s
            GROUP BY employee_id
        ) al_sum ON al_sum.employee_id = ds.employee_id
        WHERE ds.score_date = %s
        ORDER BY e.name
    """, (today, today))

    rows = cursor.fetchall()

    print(f"\n{'Employee':<25} {'Clocked':<10} {'DS Active':<12} {'Actual':<12} {'Items':<10} {'Status'}")
    print("-" * 100)

    needs_fix = []
    for r in rows:
        status = ''
        if r['ds_active'] != r['actual_active']:
            status = '*** MISMATCH - WILL FIX'
            needs_fix.append(r)
        elif r['actual_active'] == 0 and (r['ds_items'] or 0) > 0:
            status = 'No activity_logs data'

        print(f"{r['name'][:24]:<25} {r['ds_clocked'] or 0:<10} {r['ds_active'] or 0:<12} {r['actual_active']:<12} {r['ds_items'] or 0:<10} {status}")

    print("-" * 100)
    print(f"\nRecords needing fix: {len(needs_fix)}")

    if needs_fix and '--fix' in sys.argv:
        print("\nApplying fixes...")
        for r in needs_fix:
            cursor.execute("""
                UPDATE daily_scores
                SET active_minutes = %s
                WHERE employee_id = %s AND score_date = %s
            """, (r['actual_active'], r['employee_id'], today))
            print(f"  Fixed {r['name']}: {r['ds_active']} -> {r['actual_active']}")

        conn.commit()
        print(f"\n{len(needs_fix)} records updated.")
    elif needs_fix:
        print("\nRun with --fix to apply corrections.")
    else:
        print("\nNo fixes needed - all records match activity_logs data.")

    # Also check for employees with items but no activity_logs
    cursor.execute("""
        SELECT e.name, ds.items_processed
        FROM daily_scores ds
        JOIN employees e ON e.id = ds.employee_id
        WHERE ds.score_date = %s
        AND ds.items_processed > 0
        AND ds.employee_id NOT IN (
            SELECT DISTINCT employee_id FROM activity_logs
            WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = %s
        )
    """, (today, today))

    no_logs = cursor.fetchall()
    if no_logs:
        print(f"\n*** WARNING: {len(no_logs)} employees have items but NO activity_logs for today:")
        for r in no_logs:
            print(f"  - {r['name']}: {r['items_processed']} items")
        print("  These employees' active_minutes cannot be calculated from activity_logs.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_and_fix()
