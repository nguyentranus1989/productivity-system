#!/usr/bin/env python3
"""Debug clock_times query."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pymysql
from config import config

def debug():
    conn = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()

    # Check clock_times with CT timezone conversion
    cursor.execute("""
        SELECT
            e.id,
            e.name,
            ct.clock_in,
            CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago') as clock_in_ct,
            DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) as date_ct
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE ct.clock_in >= '2025-12-11' AND ct.clock_in < '2025-12-12'
        ORDER BY e.name
        LIMIT 10
    """)

    print(f"{'ID':<5} {'Name':<25} {'UTC clock_in':<22} {'CT clock_in':<22} {'CT Date'}")
    print('-' * 100)
    for row in cursor.fetchall():
        print(f"{row['id']:<5} {row['name'][:24]:<25} {str(row['clock_in']):<22} {str(row['clock_in_ct']):<22} {row['date_ct']}")

    print()

    # Now check what date matches 2025-12-11 CT
    print("Records where CT date = 2025-12-11:")
    cursor.execute("""
        SELECT
            e.id,
            e.name,
            ct.clock_in,
            CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago') as clock_in_ct
        FROM clock_times ct
        JOIN employees e ON e.id = ct.employee_id
        WHERE DATE(CONVERT_TZ(ct.clock_in, '+00:00', 'America/Chicago')) = '2025-12-11'
        ORDER BY e.name
        LIMIT 10
    """)

    for row in cursor.fetchall():
        print(f"  {row['name']}: UTC={row['clock_in']}, CT={row['clock_in_ct']}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    debug()
