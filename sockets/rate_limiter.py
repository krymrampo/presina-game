"""
Simple rate limiter for Socket.IO events.
"""
import time
from functools import wraps
from flask import request
from flask_socketio import emit


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        # sid -> {event_name: [timestamps]}
        self.requests: dict = {}
        self.cleanup_interval = 3600  # Cleanup every hour
        self.last_cleanup = time.time()
    
    def is_allowed(self, sid: str, event_name: str, max_requests: int, window_seconds: int) -> bool:
        """
        Check if request is allowed under rate limit.
        
        Args:
            sid: Socket session ID
            event_name: Name of the event
            max_requests: Maximum allowed requests in window
            window_seconds: Time window in seconds
        
        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        
        # Periodic cleanup
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(now)
        
        # Get or create entry for this sid
        if sid not in self.requests:
            self.requests[sid] = {}
        
        if event_name not in self.requests[sid]:
            self.requests[sid][event_name] = []
        
        timestamps = self.requests[sid][event_name]
        
        # Remove old timestamps outside window
        cutoff = now - window_seconds
        timestamps[:] = [t for t in timestamps if t > cutoff]
        
        # Check limit
        if len(timestamps) >= max_requests:
            return False
        
        # Add current request
        timestamps.append(now)
        return True
    
    def _cleanup_old_entries(self, now: float):
        """Remove old entries to prevent memory leaks."""
        cutoff = now - 3600  # Remove entries older than 1 hour
        
        sids_to_remove = []
        for sid, events in self.requests.items():
            events_to_remove = []
            for event_name, timestamps in events.items():
                timestamps[:] = [t for t in timestamps if t > cutoff]
                if not timestamps:
                    events_to_remove.append(event_name)
            
            for event_name in events_to_remove:
                del events[event_name]
            
            if not events:
                sids_to_remove.append(sid)
        
        for sid in sids_to_remove:
            del self.requests[sid]
        
        self.last_cleanup = now


# Global instance
rate_limiter = RateLimiter()


def rate_limit(max_requests: int = 10, window_seconds: int = 60, error_message: str = "Rate limit exceeded"):
    """
    Decorator to rate limit Socket.IO event handlers.
    
    Args:
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
        error_message: Message to send when rate limited
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            sid = request.sid
            event_name = f.__name__
            
            if not rate_limiter.is_allowed(sid, event_name, max_requests, window_seconds):
                emit('error', {'message': error_message})
                return None
            
            return f(*args, **kwargs)
        return wrapped
    return decorator
