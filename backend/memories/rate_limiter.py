"""
Simple in-memory rate limiter for DIY/homeserver deployments.
Suitable for single-server instances with moderate traffic.

Thread-safe implementation using locks to prevent race conditions.
"""

import threading
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Dict, Tuple

from django.http import JsonResponse
from django.conf import settings
from rest_framework import status


class SimpleRateLimiter:
    """
    Thread-safe in-memory rate limiter using sliding window.

    For DIY/homeserver use - tracks requests per IP address.
    Memory usage is automatically cleaned up for old entries.

    Thread Safety: Uses RLock to protect all shared state access.
    """

    def __init__(self):
        # Store request timestamps per IP: {ip: deque([timestamp1, timestamp2, ...])}
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._last_cleanup = time.time()
        self._lock = threading.RLock()  # Reentrant lock for thread safety

        # Rate limits (requests per time window)
        self.EXTRACT_LIMIT = getattr(settings, 'RATE_LIMIT_EXTRACT_PER_MINUTE', 20)  # 20 extractions per minute
        self.RETRIEVE_LIMIT = getattr(settings, 'RATE_LIMIT_RETRIEVE_PER_MINUTE', 60)  # 60 retrievals per minute
        self.WINDOW_SIZE = 60  # 1 minute window
        self.CLEANUP_INTERVAL = 300  # Clean up old entries every 5 minutes
    
    def _get_client_ip(self, request):
        """
        Get client IP address with proxy support.

        Security: Only trust X-Forwarded-For header if request comes from
        a trusted proxy to prevent IP spoofing attacks.
        """
        remote_addr = request.META.get('REMOTE_ADDR', 'unknown')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        # Get list of trusted proxy IPs from settings
        trusted_proxies = getattr(settings, 'TRUSTED_PROXY_IPS', [])

        # Only trust X-Forwarded-For if request is from a trusted proxy
        if x_forwarded_for and trusted_proxies and remote_addr in trusted_proxies:
            # Take the leftmost (client) IP from the chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Use direct connection IP
            ip = remote_addr

        return ip
    
    def _cleanup_old_entries(self):
        """
        Remove old entries to prevent memory leaks.

        Thread-safe: Protected by lock to prevent concurrent cleanup.
        """
        with self._lock:
            current_time = time.time()

            # Only cleanup periodically (check inside lock to avoid race)
            if current_time - self._last_cleanup < self.CLEANUP_INTERVAL:
                return

            cutoff_time = current_time - self.WINDOW_SIZE

            # Clean up old requests and empty IP entries
            for ip in list(self._requests.keys()):
                # Remove old timestamps from this IP's deque
                while self._requests[ip] and self._requests[ip][0] < cutoff_time:
                    self._requests[ip].popleft()

                # Remove IP entry if no recent requests
                if not self._requests[ip]:
                    del self._requests[ip]

            self._last_cleanup = current_time
    
    def _is_rate_limited(self, ip: str, limit: int) -> Tuple[bool, int]:
        """
        Check if IP is rate limited.
        Returns (is_limited, requests_in_window)

        Thread-safe: Entire check-and-update operation is atomic.
        This prevents race conditions where multiple concurrent requests
        could all pass the limit check before any add their timestamp.
        """
        with self._lock:  # CRITICAL: Protect entire check-and-update operation
            current_time = time.time()
            cutoff_time = current_time - self.WINDOW_SIZE

            # Clean up old requests for this IP
            while self._requests[ip] and self._requests[ip][0] < cutoff_time:
                self._requests[ip].popleft()

            requests_in_window = len(self._requests[ip])

            if requests_in_window >= limit:
                # Rate limit exceeded - don't add timestamp
                return True, requests_in_window

            # Within limit - add current request timestamp
            self._requests[ip].append(current_time)
            return False, requests_in_window + 1
    
    def check_extract_limit(self, request):
        """Check rate limit for memory extraction endpoint"""
        self._cleanup_old_entries()
        ip = self._get_client_ip(request)
        is_limited, count = self._is_rate_limited(ip, self.EXTRACT_LIMIT)
        
        if is_limited:
            return JsonResponse({
                'success': False,
                'error': f'Rate limit exceeded. Maximum {self.EXTRACT_LIMIT} memory extractions per minute.',
                'retry_after': 60,
                'current_count': count
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        return None
    
    def check_retrieve_limit(self, request):
        """Check rate limit for memory retrieval endpoint"""
        self._cleanup_old_entries()
        ip = self._get_client_ip(request)
        is_limited, count = self._is_rate_limited(ip, self.RETRIEVE_LIMIT)
        
        if is_limited:
            return JsonResponse({
                'success': False,
                'error': f'Rate limit exceeded. Maximum {self.RETRIEVE_LIMIT} memory retrievals per minute.',
                'retry_after': 60,
                'current_count': count
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        return None
    
    def get_stats(self):
        """
        Get current rate limiter statistics.

        Thread-safe: Protected by lock for consistent snapshot.
        """
        self._cleanup_old_entries()  # This already uses lock internally
        with self._lock:
            return {
                'active_ips': len(self._requests),
                'total_recent_requests': sum(len(deque_) for deque_ in self._requests.values()),
                'extract_limit': self.EXTRACT_LIMIT,
                'retrieve_limit': self.RETRIEVE_LIMIT,
                'window_size_seconds': self.WINDOW_SIZE
            }


# Global rate limiter instance
rate_limiter = SimpleRateLimiter()


def rate_limit_extract(view_func):
    """Decorator to apply extraction rate limiting"""
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        # Check rate limit
        limit_response = rate_limiter.check_extract_limit(request)
        if limit_response:
            return limit_response
        
        # Proceed with original view
        return view_func(self, request, *args, **kwargs)
    
    return wrapper


def rate_limit_retrieve(view_func):
    """Decorator to apply retrieval rate limiting"""
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        # Check rate limit
        limit_response = rate_limiter.check_retrieve_limit(request)
        if limit_response:
            return limit_response
        
        # Proceed with original view
        return view_func(self, request, *args, **kwargs)
    
    return wrapper