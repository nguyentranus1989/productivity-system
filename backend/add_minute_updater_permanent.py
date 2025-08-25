#!/usr/bin/env python3
"""
Add permanent minute updater to app.py
"""

with open('app.py', 'r') as f:
    lines = f.readlines()

# Find where to add the function (after the init_schedulers definition)
function_added = False
job_added = False

# The update function to add
update_function = '''
def update_active_workers_minutes():
    """Update total_minutes for all active workers"""
    from database import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clock_times 
            SET total_minutes = TIMESTAMPDIFF(MINUTE, clock_in, NOW()),
                updated_at = NOW()
            WHERE clock_out IS NULL 
            AND DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = CURDATE()
        """)
        
        updated_count = cursor.rowcount
        conn.commit()
        
        if updated_count > 0:
            print(f"Updated total_minutes for {updated_count} active workers")
        
        cursor.close()
        conn.close()
        return updated_count
        
    except Exception as e:
        print(f"Error updating active workers minutes: {e}")
        return 0

'''

# Find the line to insert the function (right before init_schedulers)
for i, line in enumerate(lines):
    if 'def init_schedulers(app):' in line and not function_added:
        # Add the function before init_schedulers
        lines.insert(i, update_function)
        function_added = True
        print(f"✓ Added update function before line {i+1}")
        break

# Now find where to add the scheduled job (after the connecteam jobs)
for i, line in enumerate(lines):
    if '"Connecteam auto-sync enabled"' in line and not job_added:
        # Add our job right before this line
        job_code = '''
        # Update active workers' minutes every 5 minutes
        background_scheduler.add_job(
            func=update_active_workers_minutes,
            trigger="interval",
            minutes=5,
            id='update_active_minutes',
            name='Update active workers minutes',
            replace_existing=True
        )
        app.logger.info("Active minutes updater scheduled")
        
'''
        lines.insert(i, job_code)
        job_added = True
        print(f"✓ Added scheduled job before line {i+1}")
        break

# Write the modified file
with open('app.py', 'w') as f:
    f.writelines(lines)

print("\n✓ Successfully added minute updater to app.py")
print("✓ Will update total_minutes every 5 minutes for active workers")
