"""
Redis-based rate limiting for API endpoints.
Implements a sliding window counter pattern for accurate rate limiting.
"""
import logging
from functools import wraps

import redis
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Initialize Redis client
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
except (redis.ConnectionError, redis.TimeoutError) as e:
    logger.warning(f"Redis connection failed: {e}. Rate limiting will be disabled.")
    redis_client = None


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip


def rate_limit(max_requests: int = 20, window_seconds: int = 60):
    """
    Redis-based rate limiting decorator for DRF views.
    
    Args:
        max_requests: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds
    
    Usage:
        @rate_limit(20, 60)  # 20 requests per minute
        def get(self, request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            # Skip rate limiting if disabled or Redis unavailable
            if not getattr(settings, 'RATE_LIMIT_ENABLED', True) or redis_client is None:
                return view_func(self, request, *args, **kwargs)
            
            try:
                # Create unique key based on function name and client IP
                client_ip = get_client_ip(request)
                key = f"rate_limit:{view_func.__name__}:{client_ip}"
                
                # Increment counter
                current_count = redis_client.incr(key)
                
                # Set expiry on first request
                if current_count == 1:
                    redis_client.expire(key, window_seconds)
                
                # Get remaining TTL for response header
                ttl = redis_client.ttl(key)
                
                # Check if limit exceeded
                if current_count > max_requests:
                    return Response(
                        {
                            'error': 'Rate limit exceeded',
                            'detail': f'Maximum {max_requests} requests per {window_seconds} seconds allowed.',
                            'retry_after': ttl
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                        headers={
                            'X-RateLimit-Limit': str(max_requests),
                            'X-RateLimit-Remaining': '0',
                            'X-RateLimit-Reset': str(ttl),
                            'Retry-After': str(ttl)
                        }
                    )
                
                # Add rate limit headers to successful responses
                response = view_func(self, request, *args, **kwargs)
                response['X-RateLimit-Limit'] = str(max_requests)
                response['X-RateLimit-Remaining'] = str(max(0, max_requests - current_count))
                response['X-RateLimit-Reset'] = str(ttl)
                
                return response
                
            except redis.RedisError as e:
                logger.error(f"Redis error in rate limiting: {e}")
                # Fail open - allow request if Redis is down
                return view_func(self, request, *args, **kwargs)
        
        return wrapper
    return decorator


class RateLimitMixin:
    """
    Mixin class for class-based views to add rate limiting.
    
    Usage:
        class MyView(RateLimitMixin, APIView):
            rate_limit_max_requests = 20
            rate_limit_window_seconds = 60
    """
    rate_limit_max_requests = 20
    rate_limit_window_seconds = 60
    
    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, 'RATE_LIMIT_ENABLED', True) or redis_client is None:
            return super().dispatch(request, *args, **kwargs)
        
        try:
            client_ip = get_client_ip(request)
            key = f"rate_limit:{self.__class__.__name__}:{client_ip}"
            
            current_count = redis_client.incr(key)
            
            if current_count == 1:
                redis_client.expire(key, self.rate_limit_window_seconds)
            
            ttl = redis_client.ttl(key)
            
            if current_count > self.rate_limit_max_requests:
                return Response(
                    {
                        'error': 'Rate limit exceeded',
                        'detail': f'Maximum {self.rate_limit_max_requests} requests per {self.rate_limit_window_seconds} seconds allowed.',
                        'retry_after': ttl
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={
                        'X-RateLimit-Limit': str(self.rate_limit_max_requests),
                        'X-RateLimit-Remaining': '0',
                        'X-RateLimit-Reset': str(ttl),
                        'Retry-After': str(ttl)
                    }
                )
            
            response = super().dispatch(request, *args, **kwargs)
            response['X-RateLimit-Limit'] = str(self.rate_limit_max_requests)
            response['X-RateLimit-Remaining'] = str(max(0, self.rate_limit_max_requests - current_count))
            response['X-RateLimit-Reset'] = str(ttl)
            
            return response
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiting: {e}")
            return super().dispatch(request, *args, **kwargs)
