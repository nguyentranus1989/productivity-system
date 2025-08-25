#!/usr/bin/env python3
"""
PERMANENT FIX for all Connecteam sync scripts
Problem: Connecteam returns UTC times, but our scripts think they're Central and convert them again
Solution: Remove the conversion since times are already UTC
"""
import os
import re
import subprocess

print("=== FIXING ALL CONNECTEAM SYNC SCRIPTS ===\n")

# List of files that need fixing
files_to_fix = [
    'auto_reconciliation.py',
    'connecteam_reconciliation.py', 
    'daily_reconciliation.py',
    'reconciliation_cron.py',
    'integrations/connecteam_sync.py'
]

for filename in files_to_fix:
    filepath = f'/var/www/productivity-system/backend/{filename}'
    
    if not os.path.exists(filepath):
        print(f"⚠️  {filename} not found")
        continue
    
    print(f"Fixing {filename}...")
    
    # Backup original
    backup_path = f"{filepath}.backup_timezone_fix"
    subprocess.run(['cp', filepath, backup_path])
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Fix patterns where we incorrectly convert Connecteam times to UTC
    replacements = [
        # Pattern 1: convert_to_utc(shift.clock_in)
        (r'clock_in_utc = self\.convert_to_utc\(shift\.clock_in\)',
         'clock_in_utc = shift.clock_in  # Already UTC from Connecteam'),
        
        # Pattern 2: convert_to_utc(shift.clock_out)
        (r'clock_out_utc = self\.convert_to_utc\(shift\.clock_out\) if shift\.clock_out else None',
         'clock_out_utc = shift.clock_out  # Already UTC from Connecteam'),
        
        # Pattern 3: Any localize to Central then to UTC (double conversion)
        (r'central_tz\.localize\(shift\.clock_in\)\.astimezone\(pytz\.UTC\)',
         'shift.clock_in  # Already UTC'),
        
        # Pattern 4: Simple convert_to_utc calls
        (r'self\.convert_to_utc\(clock_in\)',
         'clock_in  # Already UTC'),
         
        # Pattern 5: For connecteam_sync.py specifically
        (r'clock_in_utc = central_tz\.localize\(shift\.clock_in\)\.astimezone\(pytz\.UTC\)',
         'clock_in_utc = shift.clock_in  # Already UTC from Connecteam'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✓ Fixed (backup saved as {backup_path})")
    else:
        print(f"  ✓ Already correct or patterns not found")

print("\n=== TESTING THE FIX ===")

# Clear today's data and reimport
import mysql.connector

conn = mysql.connector.connect(
    host='db-mysql-sgp1-61022-do-user-16860331-0.h.db.ondigitalocean.com',
    port=25060,
    user='doadmin',
    password='AVNS_OWqdUdZ2Nw_YCkGI5Eu',
    database='productivity_tracker'
)
cursor = conn.cursor()

print("\nClearing today's data...")
cursor.execute("""
    DELETE FROM clock_times 
    WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = CURDATE()
""")
print(f"Deleted {cursor.rowcount} records")

conn.commit()
cursor.close()
conn.close()

print("\n=== NEXT STEPS ===")
print("1. Run: python3 auto_reconciliation.py --date 2025-08-13")
print("2. Verify times are correct")
print("3. Restart PM2 process: pm2 restart podfactory-sync")
print("4. The midnight cron job will now work correctly")
