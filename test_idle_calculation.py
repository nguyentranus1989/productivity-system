#!/usr/bin/env python3
"""Test script to verify idle calculation before and after fix"""

import sys
import os
sys.path.append('/var/www/productivity-system/backend')

from database.db_manager import DatabaseManager
from datetime import datetime, date

def test_employee_idle(employee_name):
    """Test idle calculation for specific employee"""
    db = DatabaseManager()
    
    # Get employee data
    query = """
        SELECT 
            e.id,
            e.name,
            ds.clocked_minutes,
            ds.active_minutes,
            ds.efficiency_rate,
            ds.items_processed
        FROM employees e
        LEFT JOIN daily_scores ds ON ds.employee_id = e.id AND ds.score_date = CURDATE()
        WHERE e.name = %s
    """
    
    result = db.execute_one(query, (employee_name,))
    
    if result:
        print(f"\n{employee_name} - CURRENT CALCULATION:")
        print(f"  Clocked: {result['clocked_minutes']} minutes")
        print(f"  Active: {result['active_minutes']} minutes")
        print(f"  Idle: {result['clocked_minutes'] - result['active_minutes'] if result['clocked_minutes'] and result['active_minutes'] else 'N/A'} minutes")
        print(f"  Efficiency: {result['efficiency_rate']}%")
        print(f"  Items: {result['items_processed']}")
    
    # Get clock sessions
    clock_query = """
        SELECT 
            clock_in,
            clock_out,
            TIMESTAMPDIFF(MINUTE, clock_in, COALESCE(clock_out, NOW())) as session_minutes
        FROM clock_times
        WHERE employee_id = (SELECT id FROM employees WHERE name = %s)
        AND DATE(clock_in) = CURDATE()
        ORDER BY clock_in
    """
    
    sessions = db.execute_query(clock_query, (employee_name,))
    print(f"\n  Clock Sessions: {len(sessions)}")
    for i, session in enumerate(sessions, 1):
        print(f"    Session {i}: {session['clock_in']} to {session['clock_out'] or 'NOW'} ({session['session_minutes']} min)")
    
    # Get activities
    activity_query = """
        SELECT 
            window_start,
            window_end,
            items_count,
            activity_type
        FROM activity_logs
        WHERE employee_id = (SELECT id FROM employees WHERE name = %s)
        AND DATE(window_start) = CURDATE()
        ORDER BY window_start
    """
    
    activities = db.execute_query(activity_query, (employee_name,))
    print(f"\n  Activities: {len(activities)}")
    for act in activities:
        print(f"    {act['window_start']} - {act['activity_type']}: {act['items_count']} items")

# Test problem employees
test_employee_idle('Huu Nguyen')
test_employee_idle('Man Nguyen')
test_employee_idle('dung duong')
