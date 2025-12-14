"""API authentication and rate limiting"""
from typing import Dict
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime, timedelta
import hashlib
import hmac
from config import Config
from database.cache_manager import get_cache_manager
cache = get_cache_manager()
import logging

logger = logging.getLogger(__name__)

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = None
        
        # Check header first
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        # Check query parameter as fallback
        elif 'api_key' in request.args:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Validate API key
        if api_key != Config.API_KEY:
            logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Store in g for potential use in endpoint
        g.api_key = api_key
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_signature(f):
    """Decorator to require request signature for sensitive endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get signature from header
        signature = request.headers.get('X-Signature')
        if not signature:
            return jsonify({'error': 'Request signature required'}), 401
        
        # Get timestamp
        timestamp = request.headers.get('X-Timestamp')
        if not timestamp:
            return jsonify({'error': 'Timestamp required'}), 401
        
        # Check timestamp is recent (within 5 minutes)
        try:
            request_time = datetime.fromisoformat(timestamp)
            if abs((datetime.now() - request_time).total_seconds()) > 300:
                return jsonify({'error': 'Request timestamp too old'}), 401
        except:
            return jsonify({'error': 'Invalid timestamp format'}), 401
        
        # Recreate signature
        body = request.get_data(as_text=True)
        message = f"{timestamp}:{body}"
        expected_signature = hmac.new(
            Config.SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


class RateLimiter:
    """Simple rate limiter using Redis"""
    
    def __init__(self, requests_per_minute=60):
        self.requests_per_minute = requests_per_minute
        self.cache = cache
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed under rate limit"""
        key = f"rate_limit:{identifier}"
        
        try:
            # Get current count
            current = self.cache.redis_client.get(key)
            
            if current is None:
                # First request, set counter
                self.cache.redis_client.setex(key, 60, 1)
                return True
            
            current_count = int(current)
            if current_count >= self.requests_per_minute:
                return False
            
            # Increment counter
            self.cache.redis_client.incr(key)
            return True
            
        except Exception as e:
            logger.critical(f"Rate limiter error - failing closed: {e}")
            # Fail closed for security - deny request if Redis unavailable
            return False
    
    def get_limit_info(self, identifier: str) -> Dict:
        """Get current rate limit information"""
        key = f"rate_limit:{identifier}"
        
        try:
            current = self.cache.redis_client.get(key)
            ttl = self.cache.redis_client.ttl(key)
            
            current_count = int(current) if current else 0
            
            return {
                'limit': self.requests_per_minute,
                'remaining': max(0, self.requests_per_minute - current_count),
                'reset_in': ttl if ttl > 0 else 60
            }
        except:
            return {
                'limit': self.requests_per_minute,
                'remaining': self.requests_per_minute,
                'reset_in': 60
            }


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(requests_per_minute=60):
    """Decorator for rate limiting endpoints"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use IP address as identifier
            identifier = request.remote_addr
            
            # Check if API key is present (higher limits for authenticated requests)
            if hasattr(g, 'api_key') and g.api_key:
                identifier = f"api:{g.api_key[:8]}"
                # Allow more requests for API users
                limiter = RateLimiter(requests_per_minute * 2)
            else:
                limiter = RateLimiter(requests_per_minute)
            
            if not limiter.is_allowed(identifier):
                limit_info = limiter.get_limit_info(identifier)
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'limit': limit_info['limit'],
                    'reset_in': limit_info['reset_in']
                }), 429
            
            # Add rate limit headers
            limit_info = limiter.get_limit_info(identifier)
            response = f(*args, **kwargs)
            
            # Handle different response types
            if isinstance(response, tuple):
                response_obj, status_code = response
            else:
                response_obj = response
                status_code = 200
            
            # Convert to Response object if needed
            from flask import make_response
            if not hasattr(response_obj, 'headers'):
                response_obj = make_response(response_obj)
            
            # Add headers
            response_obj.headers['X-RateLimit-Limit'] = str(limit_info['limit'])
            response_obj.headers['X-RateLimit-Remaining'] = str(limit_info['remaining'])
            response_obj.headers['X-RateLimit-Reset'] = str(limit_info['reset_in'])
            
            if isinstance(response, tuple):
                return response_obj, status_code
            return response_obj
        
        return decorated_function
    return decorator
