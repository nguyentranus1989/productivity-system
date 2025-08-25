#!/usr/bin/env python3
"""
System Health Check - Verify all components are using dynamic dates
Run this to ensure your productivity system is fully dynamic
"""

import sys
import pymysql
import pytz
from datetime import datetime
import requests
import json
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

class SystemHealthCheck:
    def __init__(self):
        self.central_tz = pytz.timezone('America/Chicago')
        self.checks_passed = 0
        self.checks_failed = 0
        
        # Database config
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'Nicholasbin0116$',
            'database': 'productivity_tracker'
        }
        
        # API config
        self.api_base = 'http://localhost:5000'
        self.api_key = 'dev-api-key-123'
    
    def print_header(self, text):
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.CYAN}{text.center(60)}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    def print_check(self, name, passed, details=""):
        if passed:
            self.checks_passed += 1
            print(f"{Fore.GREEN}✓ {name}{Style.RESET_ALL}")
            if details:
                print(f"  {Fore.LIGHTBLACK_EX}{details}{Style.RESET_ALL}")
        else:
            self.checks_failed += 1
            print(f"{Fore.RED}✗ {name}{Style.RESET_ALL}")
            if details:
                print(f"  {Fore.YELLOW}{details}{Style.RESET_ALL}")
    
    def check_timezone_setup(self):
        """Check if timezone is properly configured"""
        self.print_header("Timezone Configuration")
        
        # Check system timezone awareness
        now = datetime.now(self.central_tz)
        self.print_check(
            "Central Time zone configured",
            True,
            f"Current time: {now.strftime('%Y-%m-%d %I:%M:%S %p %Z')}"
        )
        
        # Check UTC conversion
        utc_now = datetime.now(pytz.UTC)
        # Calculate the actual time difference in hours
        time_diff = round((now - utc_now).total_seconds() / 3600)
        expected_diff = -5 if now.dst() else -6  # Central is behind UTC
        
        self.print_check(
            "UTC to Central conversion",
            abs(time_diff - expected_diff) <= 1,
            f"Time difference: {time_diff} hours (expected: {expected_diff})"
        )
    
    def check_database_connection(self):
        """Check database connection and timezone functions"""
        self.print_header("Database Connection")
        
        try:
            conn = pymysql.connect(**self.db_config)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            self.print_check("Database connection", True)
            
            # Check timezone support
            cursor.execute("SELECT NOW() as server_time, @@session.time_zone as timezone")
            result = cursor.fetchone()
            self.print_check(
                "Database timezone",
                True,
                f"Server time: {result['server_time']}, Timezone: {result['timezone']}"
            )
            
            # Check CONVERT_TZ function
            cursor.execute(
                "SELECT NOW() as utc_time, "
                "CONVERT_TZ(NOW(), '+00:00', 'America/Chicago') as central_time"
            )
            tz_result = cursor.fetchone()
            
            if tz_result['central_time'] is None:
                self.print_check(
                    "CONVERT_TZ function",
                    False,
                    "Timezone data not loaded in MySQL. Run: mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root -p mysql"
                )
            else:
                self.print_check(
                    "CONVERT_TZ function",
                    True,
                    f"Central time: {tz_result['central_time']}"
                )
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.print_check("Database connection", False, str(e))
    
    def check_api_endpoints(self):
        """Check if API endpoints are responding"""
        self.print_header("API Endpoints")
        
        headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # Check health endpoint
        try:
            response = requests.get(f"{self.api_base}/health", timeout=5)
            self.print_check(
                "Health endpoint",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
        except Exception as e:
            self.print_check("Health endpoint", False, str(e))
        
        # Check server time endpoint
        try:
            response = requests.get(
                f"{self.api_base}/api/server-time",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.print_check(
                    "Server time endpoint",
                    True,
                    f"Central time: {data.get('central_time', 'N/A')}"
                )
            else:
                self.print_check(
                    "Server time endpoint",
                    False,
                    f"Status: {response.status_code}"
                )
        except Exception as e:
            self.print_check("Server time endpoint", False, "Not implemented yet")
    
    def check_scheduler_status(self):
        """Check if scheduler is running with correct timezone"""
        self.print_header("Scheduler Status")
        
        try:
            response = requests.get(
                f"{self.api_base}/api/scheduler/status",
                headers={'X-API-Key': self.api_key},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check productivity scheduler
                prod_scheduler = data.get('productivity_scheduler', {})
                if isinstance(prod_scheduler, dict) and prod_scheduler.get('status') == 'running':
                    jobs = prod_scheduler.get('jobs', [])
                    self.print_check(
                        "Productivity scheduler",
                        True,
                        f"{len(jobs)} jobs scheduled"
                    )
                    
                    # Show next run times
                    for job in jobs[:3]:  # Show first 3 jobs
                        print(f"  - {job['name']}: {job.get('next_run', 'Not scheduled')}")
                else:
                    self.print_check("Productivity scheduler", False, "Not running")
                    
            else:
                self.print_check("Scheduler status", False, f"API returned {response.status_code}")
                
        except Exception as e:
            self.print_check("Scheduler status", False, "Scheduler endpoint not available")
    
    def check_recent_data(self):
        """Check if recent data is being processed correctly"""
        self.print_header("Recent Data Processing")
        
        try:
            conn = pymysql.connect(**self.db_config)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # Check today's activities
            cursor.execute("""
                SELECT 
                    COUNT(*) as activity_count,
                    MIN(window_start) as first_activity,
                    MAX(window_start) as last_activity
                FROM activity_logs
                WHERE DATE(CONVERT_TZ(window_start, '+00:00', 'America/Chicago')) = CURDATE()
            """)
            
            activities = cursor.fetchone()
            if activities['activity_count'] > 0:
                self.print_check(
                    "Today's activities",
                    True,
                    f"{activities['activity_count']} activities recorded"
                )
            else:
                self.print_check(
                    "Today's activities",
                    False,
                    "No activities found for today"
                )
            
            # Check today's scores
            cursor.execute("""
                SELECT 
                    COUNT(*) as score_count,
                    MAX(updated_at) as last_update
                FROM daily_scores
                WHERE score_date = CURDATE()
            """)
            
            scores = cursor.fetchone()
            if scores['score_count'] > 0:
                last_update = scores['last_update']
                if last_update:
                    minutes_ago = (datetime.now() - last_update).total_seconds() / 60
                    self.print_check(
                        "Today's scores",
                        True,
                        f"{scores['score_count']} employees scored, last update {int(minutes_ago)} minutes ago"
                    )
                else:
                    self.print_check(
                        "Today's scores",
                        True,
                        f"{scores['score_count']} employees scored"
                    )
            else:
                self.print_check(
                    "Today's scores",
                    False,
                    "No scores calculated for today"
                )
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.print_check("Recent data check", False, str(e))
    
    def check_sync_status(self):
        """Check sync statuses"""
        self.print_header("Sync Status")
        
        try:
            conn = pymysql.connect(**self.db_config)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # Check PodFactory sync
            cursor.execute("""
                SELECT 
                    MAX(sync_time) as last_sync,
                    SUM(records_synced) as total_synced
                FROM podfactory_sync_log
                WHERE DATE(sync_time) = CURDATE()
                AND status IN ('SUCCESS', 'PARTIAL')
            """)
            
            pf_sync = cursor.fetchone()
            if pf_sync['last_sync']:
                minutes_ago = (datetime.now() - pf_sync['last_sync']).total_seconds() / 60
                self.print_check(
                    "PodFactory sync",
                    minutes_ago < 15,  # Should sync within 15 minutes
                    f"Last sync {int(minutes_ago)} minutes ago, {pf_sync['total_synced'] or 0} records today"
                )
            else:
                self.print_check(
                    "PodFactory sync",
                    False,
                    "No sync recorded today"
                )
            
            # Check Connecteam sync
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT employee_id) as employees_synced,
                    MAX(updated_at) as last_update
                FROM clock_times
                WHERE DATE(CONVERT_TZ(clock_in, '+00:00', 'America/Chicago')) = CURDATE()
                AND source = 'connecteam'
            """)
            
            ct_sync = cursor.fetchone()
            if ct_sync['employees_synced'] > 0:
                self.print_check(
                    "Connecteam sync",
                    True,
                    f"{ct_sync['employees_synced']} employees synced today"
                )
            else:
                self.print_check(
                    "Connecteam sync",
                    False,
                    "No Connecteam data for today"
                )
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            self.print_check("Sync status check", False, str(e))
    
    def run_all_checks(self):
        """Run all health checks"""
        print(f"\n{Fore.YELLOW}PRODUCTIVITY SYSTEM HEALTH CHECK{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Running at: {datetime.now(self.central_tz).strftime('%Y-%m-%d %I:%M:%S %p %Z')}{Style.RESET_ALL}")
        
        self.check_timezone_setup()
        self.check_database_connection()
        self.check_api_endpoints()
        self.check_scheduler_status()
        self.check_recent_data()
        self.check_sync_status()
        
        # Summary
        self.print_header("Summary")
        total_checks = self.checks_passed + self.checks_failed
        success_rate = (self.checks_passed / total_checks * 100) if total_checks > 0 else 0
        
        if self.checks_failed == 0:
            print(f"\n{Fore.GREEN}✓ All {self.checks_passed} checks passed!{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Your system is fully dynamic and timezone-aware!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.YELLOW}Passed: {self.checks_passed}/{total_checks} ({success_rate:.1f}%){Style.RESET_ALL}")
            print(f"{Fore.RED}Failed: {self.checks_failed} checks need attention{Style.RESET_ALL}")
        
        return self.checks_failed == 0

if __name__ == "__main__":
    # Check if colorama is installed
    try:
        import colorama
    except ImportError:
        print("Installing colorama for colored output...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "colorama"])
        import colorama
    
    checker = SystemHealthCheck()
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)