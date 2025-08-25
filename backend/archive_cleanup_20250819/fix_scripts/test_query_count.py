import time
import sys
sys.path.append('/var/www/productivity-system/backend')
from database.db_manager import DatabaseManager

db = DatabaseManager()

# Test a simple query and measure time
start = time.time()
result = db.execute_one("SELECT 1")
end = time.time()
print(f"Single query latency: {(end-start)*1000:.0f}ms")

# Test 10 queries
start = time.time()
for i in range(10):
    result = db.execute_one("SELECT 1")
end = time.time()
print(f"10 queries total: {(end-start)*1000:.0f}ms")
print(f"Average per query: {(end-start)*100:.0f}ms")
