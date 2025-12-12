"""Diagnose which imports are slow"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("IMPORT TIME DIAGNOSIS")
print("=" * 60)

start = time.time()

def timed_import(module_name):
    s = time.time()
    try:
        __import__(module_name)
        elapsed = time.time() - s
        print(f"[{elapsed:.2f}s] {module_name}")
    except Exception as e:
        elapsed = time.time() - s
        print(f"[{elapsed:.2f}s] {module_name} - ERROR: {e}")

# Base imports
print("\n--- Base imports ---")
timed_import("dotenv")
from dotenv import load_dotenv
load_dotenv()

timed_import("flask")
timed_import("flask_cors")
timed_import("logging")
timed_import("datetime")
timed_import("apscheduler.schedulers.background")

# Config
print("\n--- Config ---")
timed_import("config")

# Database
print("\n--- Database ---")
timed_import("database.db_manager")

# API Blueprints
print("\n--- API Blueprints ---")
timed_import("api.activities")
timed_import("api.cache")
timed_import("api.flags")
timed_import("api.trends")
timed_import("api.schedule")
timed_import("api.idle")
timed_import("api.gamification")
timed_import("api.team_metrics")
timed_import("api.connecteam")
timed_import("api.dashboard")
timed_import("api.employee_auth")
timed_import("api.admin_auth")
timed_import("api.system_control")

print("\n" + "=" * 60)
print(f"TOTAL TIME: {time.time() - start:.2f}s")
print("=" * 60)
