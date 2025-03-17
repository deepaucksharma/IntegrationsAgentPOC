"""Rate limiting functionality."""
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class RateLimit:
    """Rate limit configuration."""
    max_requests: int
    window_seconds: int

class RateLimiter:
    """Implements rate limiting for workflow executions."""
    
    def __init__(self):
        """Initialize the rate limiter."""
        self.requests: Dict[str, list] = defaultdict(list)
        self.limits: Dict[str, RateLimit] = {}
        self.default_limit = RateLimit(max_requests=100, window_seconds=60)
    
    def set_limit(self, key: str, max_requests: int, window_seconds: int) -> None:
        """Set a rate limit for a specific key."""
        self.limits[key] = RateLimit(max_requests, window_seconds)
        logger.info(f"Set rate limit for {key}: {max_requests} requests per {window_seconds} seconds")
    
    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed under the rate limit."""
        try:
            limit = self.limits.get(key, self.default_limit)
            now = time.time()
            
            # Remove old requests outside the window
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if now - req_time <= limit.window_seconds
            ]
            
            # Check if we're under the limit
            if len(self.requests[key]) >= limit.max_requests:
                logger.warning(f"Rate limit exceeded for {key}")
                return False
            
            # Record the new request
            self.requests[key].append(now)
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {key}: {e}")
            # Fail open on error
            return True
    
    def get_usage(self, key: str) -> Dict[str, Any]:
        """Get current usage statistics for a key."""
        try:
            limit = self.limits.get(key, self.default_limit)
            now = time.time()
            
            # Clean up old requests
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if now - req_time <= limit.window_seconds
            ]
            
            return {
                'current_requests': len(self.requests[key]),
                'max_requests': limit.max_requests,
                'window_seconds': limit.window_seconds,
                'remaining_requests': max(0, limit.max_requests - len(self.requests[key])),
                'reset_time': datetime.fromtimestamp(
                    min(self.requests[key]) + limit.window_seconds
                ).isoformat() if self.requests[key] else None
            }
        except Exception as e:
            logger.error(f"Error getting usage stats for {key}: {e}")
            return {
                'error': str(e),
                'current_requests': 0,
                'max_requests': limit.max_requests,
                'window_seconds': limit.window_seconds
            }
    
    def reset(self, key: Optional[str] = None) -> None:
        """Reset rate limiting for a key or all keys."""
        try:
            if key:
                self.requests[key] = []
                logger.info(f"Reset rate limiting for {key}")
            else:
                self.requests.clear()
                logger.info("Reset all rate limiting")
        except Exception as e:
            logger.error(f"Error resetting rate limits: {e}")
    
    def cleanup(self) -> None:
        """Clean up old request records."""
        try:
            now = time.time()
            for key in list(self.requests.keys()):
                limit = self.limits.get(key, self.default_limit)
                self.requests[key] = [
                    req_time for req_time in self.requests[key]
                    if now - req_time <= limit.window_seconds
                ]
                if not self.requests[key]:
                    del self.requests[key]
        except Exception as e:
            logger.error(f"Error cleaning up rate limits: {e}") 