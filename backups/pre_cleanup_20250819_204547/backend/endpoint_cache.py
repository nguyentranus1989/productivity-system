"""Simple endpoint result caching using Redis"""
import json
import redis
import hashlib
import time
from flask import request, jsonify

try:
    redis_client = redis.Redis(host='localhost', port=6379, db=2, decode_responses=True)
    redis_client.ping()
    CACHE_ENABLED = True
except:
    CACHE_ENABLED = False
    redis_client = None

def get_cached_response(endpoint_name, cache_seconds=10):
    """Get cached response for an endpoint"""
    if not CACHE_ENABLED:
        return None
    
    # Create cache key from endpoint and query params
    cache_key = f"endpoint:{endpoint_name}:{request.query_string.decode()}"
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            print(f"✅ Cache HIT: {endpoint_name}", flush=True)
            return json.loads(cached)
    except:
        pass
    
    print(f"🔄 Cache MISS: {endpoint_name}", flush=True)
    return None

def cache_response(endpoint_name, data, cache_seconds=10):
    """Cache response data for an endpoint"""
    if not CACHE_ENABLED or not data:
        return
    
    cache_key = f"endpoint:{endpoint_name}:{request.query_string.decode()}"
    
    try:
        redis_client.setex(cache_key, cache_seconds, json.dumps(data, default=str))
    except:
        pass
