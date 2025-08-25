"""Implement working cache for dashboard endpoints"""

# Read dashboard.py
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Add simple cache implementation at the top
cache_code = '''
# Simple in-memory cache
import time
_endpoint_cache = {}

def cached_endpoint(ttl_seconds=10):
    """Simple cache decorator"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            from flask import request
            cache_key = f"{func.__name__}:{request.full_path}"
            
            # Check cache
            if cache_key in _endpoint_cache:
                data, timestamp = _endpoint_cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    print(f"CACHE HIT: {func.__name__}", flush=True)
                    return data
            
            print(f"CACHE MISS: {func.__name__} - fetching from DB...", flush=True)
            result = func(*args, **kwargs)
            _endpoint_cache[cache_key] = (result, time.time())
            
            # Clean old entries
            if len(_endpoint_cache) > 50:
                _endpoint_cache.clear()
            
            return result
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

'''

# Insert cache code after imports
insert_pos = 0
for i in range(len(lines)):
    if 'from flask import' in lines[i]:
        insert_pos = i + 1
        break

# Check if cache already added
if '_endpoint_cache' not in ''.join(lines):
    lines.insert(insert_pos, cache_code)
    print("Added cache implementation")

# Add decorator to get_leaderboard
for i in range(len(lines)):
    if 'def get_leaderboard():' in lines[i]:
        # Check if decorator exists
        if i > 0 and 'cached_endpoint' not in lines[i-1]:
            lines.insert(i, '@cached_endpoint(ttl_seconds=10)\n')
            print("Added cache decorator to get_leaderboard")
        break

# Add to other slow endpoints
slow_endpoints = [
    ('def get_department_stats():', 15),
    ('def get_cost_analysis():', 30),
]

for endpoint, ttl in slow_endpoints:
    for i in range(len(lines)):
        if endpoint in lines[i]:
            if i > 0 and 'cached_endpoint' not in lines[i-1]:
                lines.insert(i, f'@cached_endpoint(ttl_seconds={ttl})\n')
                print(f"Added cache to {endpoint}")
            break

# Save the file
with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.writelines(lines)

print("✅ Cache implementation complete")
