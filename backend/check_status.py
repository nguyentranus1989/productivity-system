#!/usr/bin/env python3
"""
System Status Check - Fixed Version
"""

import requests
from datetime import datetime
from database.db_manager import DatabaseManager
import subprocess
import psutil

def check_mysql_service():
    """Check if MySQL is running"""
    try:
        mysql_running = any('mysql' in proc.name().lower() for proc in psutil.process_iter(['name']))
        print("✅ MySQL Service: RUNNING" if mysql_running else "❌ MySQL Service: NOT RUNNING")
        return mysql_running
    except Exception as e:
        print(f"⚠️  MySQL Service: UNKNOWN - {e}")
        return False

def check_database_connection():
    """Check database connectivity"""
    try:
        db = DatabaseManager()
        result = db.execute_query("SELECT 1")
        print("✅ Database Connection: CONNECTED")
        return True
    except Exception as e:
        print(f"❌ Database Connection: FAILED - {e}")
        return False

def check_flask_api():
    """Check if Flask API is running"""
    try:
        # Try a known endpoint instead of health
        response = requests.get("http://localhost:5000/api/dashboard/leaderboard?date=2025-08-04", 
                               headers={"X-API-Key": "dev-api-key-123"}, 
                               timeout=2)
        if response.status_code == 200:
            print("✅ Flask API: RUNNING on http://localhost:5000")
            return True
        else:
            print(f"⚠️  Flask API: Running but returned status {response.status_code}")
            return True
    except requests.exceptions.ConnectionError:
        print("❌ Flask API: NOT RUNNING")
        return False
    except Exception as e:
        print(f"❌ Flask API: ERROR - {e}")
        return False

def check_frontend_server():
    """Check if frontend server is running"""
    try:
        response = requests.get("http://localhost:8000", timeout=2)
        print("✅ Frontend Server: RUNNING on http://localhost:8000")
        return True
    except:
        print("❌ Frontend Server: NOT RUNNING")
        return False

def check_processes():
    """Check and count Python processes"""
    processes = {'flask': 0, 'sync': 0, 'frontend': 0}
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if 'python' in proc.info['name'].lower():
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'app.py' in cmdline:
                processes['flask'] += 1
            elif 'sync' in cmdline:
                processes['sync'] += 1
            elif 'http.server' in cmdline:
                processes['frontend'] += 1
    
    print(f"\n📊 Process Count:")
    print(f"  - Flask Backend: {processes['flask']} (should be 1)")
    print(f"  - PodFactory Sync: {processes['sync']} (should be 1)")
    print(f"  - Frontend Server: {processes['frontend']} (should be 1)")
    
    return processes

def check_data_freshness():
    """Check how fresh the data is"""
    try:
        db = DatabaseManager()
        
        # Check last calculation
        result = db.execute_query("SELECT MAX(updated_at) as last FROM daily_scores WHERE score_date = CURDATE()")
        last_calc = result[0]['last']
        
        if last_calc:
            minutes = int((datetime.now() - last_calc).total_seconds() / 60)
            status = "✅" if minutes < 5 else "⚠️" if minutes < 15 else "❌"
            print(f"{status} Last Calculation: {minutes} minutes ago ({last_calc.strftime('%H:%M:%S')})")
        
        # Check if sync is actually happening by looking at activity_logs
        result = db.execute_query("""
            SELECT COUNT(*) as count, MAX(window_start) as latest 
            FROM activity_logs 
            WHERE window_start > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
        """)
        
        recent_count = result[0]['count']
        if recent_count > 0:
            print(f"✅ Recent Activities: {recent_count} in last 10 minutes")
        else:
            print("❌ No Recent Activities: Sync may not be working")
        
        # Activity count today
        result = db.execute_query("SELECT COUNT(*) as total FROM activity_logs WHERE DATE(window_start) = CURDATE()")
        print(f"📈 Today's Total Activities: {result[0]['total']}")
        
        return True
    except Exception as e:
        print(f"❌ Data Check: ERROR - {e}")
        return False

def main():
    print("="*60)
    print("PRODUCTIVITY SYSTEM STATUS CHECK")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    print("\n🔍 CHECKING SERVICES...")
    print("-"*40)
    
    check_mysql_service()
    check_database_connection()
    check_flask_api()
    check_frontend_server()
    
    print("\n🔍 CHECKING DATA STATUS...")
    print("-"*40)
    
    check_data_freshness()
    
    processes = check_processes()
    
    # Check for issues
    issues = []
    if processes['flask'] == 0:
        issues.append("Flask not running")
    elif processes['flask'] > 1:
        issues.append(f"Multiple Flask instances ({processes['flask']})")
    
    if processes['sync'] == 0:
        issues.append("Sync not running")
    elif processes['sync'] > 1:
        issues.append(f"Multiple sync instances ({processes['sync']})")
    
    # Summary
    print("\n" + "="*60)
    if not issues:
        print("✅ SYSTEM STATUS: ALL GOOD!")
        print("\nAccess dashboards at:")
        print("  - Shop Floor: http://localhost:8000/shop-floor.html")
        print("  - Manager: http://localhost:8000/manager.html")
    else:
        print(f"❌ ISSUES FOUND: {len(issues)}")
        for issue in issues:
            print(f"  - {issue}")
        
        if any("Multiple" in issue for issue in issues):
            print("\n🔧 FIX: Too many processes running!")
            print("   1. Kill all: taskkill /F /IM python.exe")
            print("   2. Start fresh with your batch file")

if __name__ == "__main__":
    main()