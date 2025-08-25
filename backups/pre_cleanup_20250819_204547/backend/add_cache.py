import time

# Read dashboard.py
with open('/var/www/productivity-system/backend/api/dashboard.py', 'r') as f:
    lines = f.readlines()

# Simple cache code to add
cache_code = """
# Simple in-memory cache
import time
_endpoint_cache = {}

def cached_endpoint(ttl_seconds=10):
    def decorator(func):
        def wrapper(*args, **kwargs):
            from flask import request
            cache_key = f"{func.__name__}:{request.full_path}"
            
            if cache_key in _endpoint_cache:
                data, timestamp = _endpoint_cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    print(f"CACHE HIT: {func.__name__}", flush=True)
                    return data
            
            print(f"CACHE MISS: {func.__name__}", flush=True)
            result = func(*args, **kwargs)
            _endpoint_cache[cache_key] = (result, time.time())
            return result
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

"""

# Find where to insert
for i in range(len(lines)):
    if 'from flask import' in lines[i]:
        lines.insert(i+1, cache_code)
        print("Added cache code")
        break

# Save
with open('/var/www/productivity-system/backend/api/dashboard.py', 'w') as f:
    f.writelines(lines)
