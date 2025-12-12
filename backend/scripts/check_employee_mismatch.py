#!/usr/bin/env python3
"""Check employee name mismatches between systems."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pymysql
from config import config

def check():
    conn = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()

    # Check employees table for Abraham and dung
    print('=== EMPLOYEES TABLE ===')
    cursor.execute("""
        SELECT id, name, connecteam_user_id
        FROM employees
        WHERE LOWER(name) LIKE '%abraham%' OR LOWER(name) LIKE '%dung%' OR LOWER(name) LIKE '%duong%'
        ORDER BY name
    """)
    employees = cursor.fetchall()
    for r in employees:
        print(f"ID={r['id']}, Name='{r['name']}', connecteam_user_id={r['connecteam_user_id']}")

    emp_ids = [e['id'] for e in employees]

    # Check clock_times for these employees
    print()
    print('=== CLOCK_TIMES for 2025-12-11 ===')
    if emp_ids:
        placeholders = ','.join(['%s'] * len(emp_ids))
        cursor.execute(f"""
            SELECT e.id, e.name, ct.clock_in, ct.clock_out
            FROM clock_times ct
            JOIN employees e ON e.id = ct.employee_id
            WHERE e.id IN ({placeholders})
            AND DATE(ct.clock_in) = '2025-12-11'
        """, emp_ids)
        results = cursor.fetchall()
        if results:
            for r in results:
                print(f"{r['name']}: {r['clock_in']} - {r['clock_out']}")
        else:
            print('No clock_times found for these employee IDs')

    # Check daily_scores for these employees
    print()
    print('=== DAILY_SCORES for 2025-12-11 ===')
    if emp_ids:
        cursor.execute(f"""
            SELECT e.id, e.name, ds.clocked_minutes, ds.active_minutes, ds.items_processed
            FROM daily_scores ds
            JOIN employees e ON e.id = ds.employee_id
            WHERE e.id IN ({placeholders})
            AND ds.score_date = '2025-12-11'
        """, emp_ids)
        for r in cursor.fetchall():
            print(f"{r['name']}: clocked={r['clocked_minutes']}, active={r['active_minutes']}, items={r['items_processed']}")

    # Check if there are employees in cost-analysis that don't have clock_times
    print()
    print('=== EMPLOYEES IN COST-ANALYSIS WITHOUT CLOCK_TIMES ===')
    cursor.execute("""
        SELECT e.id, e.name
        FROM employees e
        INNER JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = '2025-12-11'
        LEFT JOIN clock_times ct ON ct.employee_id = e.id AND DATE(ct.clock_in) = '2025-12-11'
        WHERE ct.id IS NULL
        AND ds.items_processed > 0
        ORDER BY e.name
    """)
    for r in cursor.fetchall():
        print(f"ID={r['id']}, Name='{r['name']}' - HAS daily_scores but NO clock_times")

    # Check if Abraham and dung are in cost-analysis employee_ids
    print()
    print('=== CHECK CLOCK_TIMES TOOLTIP QUERY ===')
    # Simulate what dashboard.py does - get employee_ids from cost-analysis
    cursor.execute("""
        SELECT DISTINCT e.id
        FROM employees e
        INNER JOIN (
            SELECT employee_id
            FROM clock_times
            WHERE clock_in >= '2025-12-11' AND clock_in < DATE_ADD('2025-12-11', INTERVAL 1 DAY)
        ) ch ON e.id = ch.employee_id
        WHERE e.is_active = 1
    """)
    cost_emp_ids = [r['id'] for r in cursor.fetchall()]
    print(f"Employee IDs from clock_hours CTE: {len(cost_emp_ids)} employees")
    print(f"Abraham (28) in list: {28 in cost_emp_ids}")
    print(f"dung (24) in list: {24 in cost_emp_ids}")

    # Now test the tooltip query for these specific employees
    print()
    print('=== TOOLTIP QUERY TEST ===')
    cursor.execute("""
        SELECT
            ct.employee_id,
            ct.clock_in,
            ct.clock_out
        FROM clock_times ct
        WHERE ct.employee_id IN (28, 24)
        AND DATE(ct.clock_in) = '2025-12-11'
    """)
    results = cursor.fetchall()
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  emp_id={r['employee_id']}, {r['clock_in']} - {r['clock_out']}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    check()
