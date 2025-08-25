#!/usr/bin/env python3
"""
Fix the role assignment issue permanently
"""
import os
import re

def fix_dashboard_api():
    """Fix the api/dashboard.py file"""
    file_path = 'api/dashboard.py'
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Add ACTION_TO_ROLE_ID mapping if it doesn't exist
    if 'ACTION_TO_ROLE_ID' not in content:
        # Find where to insert (after PODFACTORY_ROLE_TO_CONFIG_ID)
        pattern = r'(PODFACTORY_ROLE_TO_CONFIG_ID = {[^}]+})'
        replacement = r'''\1

# Map PodFactory actions to role_configs.id
ACTION_TO_ROLE_ID = {
    'In Production': 1,      # Heat Pressing
    'QC Passed': 2,          # Packing and Shipping  
    'Picking': 3,            # Picker
    'Labeling': 4,           # Labeler
    'Film Matching': 5       # Film Matching
}'''
        content = re.sub(pattern, replacement, content)
    
    # Fix all occurrences of role_id assignment
    # Pattern to find: role_id = PODFACTORY_ROLE_TO_CONFIG_ID.get(user_role, 3)
    old_pattern = r'role_id = PODFACTORY_ROLE_TO_CONFIG_ID\.get\(user_role, 3\)'
    new_line = "role_id = metadata.get('role_id') or ACTION_TO_ROLE_ID.get(action, 3)"
    
    content = re.sub(old_pattern, new_line, content)
    
    # Save the fixed file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {file_path}")
    return True

def fix_database_today():
    """Fix today's data in the database"""
    import pymysql
    from datetime import datetime
    
    # Database connection
    conn = pymysql.connect(
        host='db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
        port=25060,
        user='doadmin',
        password='AVNS_OWqdUdZ2Nw_YCkGI5Eu',
        database='productivity_tracker'
    )
    
    cursor = conn.cursor()
    
    # Fix role_ids for today's activities
    fix_query = """
    UPDATE activity_logs 
    SET role_id = CASE 
        WHEN activity_type = 'In Production' THEN 1
        WHEN activity_type = 'QC Passed' THEN 2
        WHEN activity_type = 'Picking' THEN 3
        WHEN activity_type = 'Labeling' THEN 4
        WHEN activity_type = 'Film Matching' THEN 5
        ELSE role_id
    END
    WHERE DATE(window_start) = CURDATE()
    """
    
    cursor.execute(fix_query)
    affected = cursor.rowcount
    print(f"✅ Fixed {affected} activity records")
    
    # Recalculate today's scores
    recalc_query = """
    UPDATE daily_scores ds
    SET points_earned = (
        SELECT COALESCE(SUM(al.items_count * rc.multiplier), 0)
        FROM activity_logs al
        JOIN role_configs rc ON rc.id = al.role_id
        WHERE al.employee_id = ds.employee_id
        AND DATE(al.window_start) = ds.score_date
    ),
    updated_at = NOW()
    WHERE score_date = CURDATE()
    """
    
    cursor.execute(recalc_query)
    affected = cursor.rowcount
    print(f"✅ Recalculated scores for {affected} employees")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return True

def restart_services():
    """Restart PM2 services"""
    import subprocess
    
    try:
        subprocess.run(['pm2', 'restart', 'flask-backend'], check=True)
        print("✅ Restarted flask-backend")
    except:
        print("⚠️ Could not restart flask-backend")
    
    try:
        subprocess.run(['pm2', 'restart', 'podfactory-sync'], check=True)
        print("✅ Restarted podfactory-sync")
    except:
        print("⚠️ Could not restart podfactory-sync")
    
    return True

if __name__ == "__main__":
    print("🔧 Fixing Role Assignment Issue")
    print("-" * 40)
    
    # Fix the code
    fix_dashboard_api()
    
    # Fix today's data
    fix_database_today()
    
    # Restart services
    restart_services()
    
    print("-" * 40)
    print("✅ All fixes applied successfully!")
    print("The system should now use activity-based role assignments correctly.")
