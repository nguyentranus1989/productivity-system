import json
import redis
import hashlib
from functools import wraps

# Initialize Redis
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=1)
    redis_client.ping()
    CACHE_ENABLED = True
    print("✅ Redis cache enabled", flush=True)
except:
    CACHE_ENABLED = False
    redis_client = None
    print("⚠️ Redis not available, running without cache", flush=True)

def cache_api_result(seconds=30):
    """Cache Flask endpoint results - DO NOT use this decorator, it interferes with Flask responses"""
    def decorator(func):
        return func  # Just return the function unchanged for now
    return decorator

def cached_query(key_prefix, seconds=60):
    """Cache database query results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not CACHE_ENABLED:
                return func(*args, **kwargs)
            
            # Create cache key
            cache_key = f"{key_prefix}:{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()[:8]}"
            
            # Try to get from cache
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    print(f"✅ Cache hit: {cache_key}", flush=True)
                    return json.loads(cached)
            except:
                pass
            
            # Get fresh data
            print(f"🔄 Cache miss: {cache_key}", flush=True)
            result = func(*args, **kwargs)
            
            # Store in cache
            try:
                if result is not None:
                    redis_client.setex(cache_key, seconds, json.dumps(result, default=str))
            except:
                pass
            
            return result
        return wrapper
    return decorator
