#!/usr/bin/env python3
from db_config import DB_CONFIG
import mysql.connector

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Test query
    cursor.execute("SELECT COUNT(*) as count FROM order_predictions WHERE actual_orders IS NOT NULL")
    result = cursor.fetchone()
    
    print(f"✅ Connection successful!")
    print(f"📊 Found {result[0]} days of historical data")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
