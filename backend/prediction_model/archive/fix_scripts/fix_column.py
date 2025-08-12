#!/usr/bin/env python3
"""
Add missing column to predictions_enhanced table
"""

from db_config import DB_CONFIG
import mysql.connector

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

print("🔧 Checking and fixing table...")

# Check if column exists
cursor.execute("""
    SELECT COUNT(*) 
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'productivity_tracker' 
    AND TABLE_NAME = 'predictions_enhanced' 
    AND COLUMN_NAME = 'real_demand'
""")

result = cursor.fetchone()

if result[0] == 0:
    print("Adding real_demand column...")
    cursor.execute("ALTER TABLE predictions_enhanced ADD COLUMN real_demand INT")
    conn.commit()
    print("✅ Column added!")
else:
    print("✅ Column already exists!")

cursor.close()
conn.close()

print("\n🚀 Now running deployment with clear numbers...")
import subprocess
subprocess.run(['python3', 'deploy_enhanced.py'])
