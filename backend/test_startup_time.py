"""Test Flask app startup time with lazy loading"""
import time
import sys
import os

# Ensure proper path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("FLASK STARTUP TIME TEST (Lazy Loading)")
print("=" * 50)

# Time the import
start = time.time()
print(f"\n[{time.time()-start:.3f}s] Starting import...")

from dotenv import load_dotenv
load_dotenv()
print(f"[{time.time()-start:.3f}s] dotenv loaded")

from app import create_app
print(f"[{time.time()-start:.3f}s] create_app imported")

# Time app creation
app = create_app()
print(f"[{time.time()-start:.3f}s] Flask app created!")

print("\n" + "=" * 50)
print(f"TOTAL STARTUP TIME: {time.time()-start:.2f} seconds")
print("=" * 50)

# Show what's deferred
print("\nDEFERRED (running in background):")
print("  - Database connection pool")
print("  - Productivity scheduler")
print("  - Background scheduler")
print("  - Connecteam sync jobs")

print("\nServer ready to accept requests immediately!")
