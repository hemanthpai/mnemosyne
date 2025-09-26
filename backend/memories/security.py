"""
Security enhancements for DIY/homeserver deployments.
Simple middleware and utilities for basic security.
"""

import hashlib
import hmac
import time
from typing import Optional

from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds basic security headers for DIY deployments.
    Lightweight and doesn't require external dependencies.
    """
    
    def process_response(self, request, response):
        # Basic security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Don't cache sensitive API responses
        if request.path.startswith('/api/'):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response


class BasicAPIKeyMixin:
    """
    Simple API key authentication for DIY setups.
    Can be used by views that need basic protection.
    """
    
    def get_api_key_from_request(self, request) -> Optional[str]:
        """Extract API key from request headers or query params"""
        # Check Authorization header: "Bearer <api_key>" or "API-Key <api_key>"
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        elif auth_header.startswith('API-Key '):
            return auth_header[8:]
        
        # Check X-API-Key header
        api_key = request.META.get('HTTP_X_API_KEY')
        if api_key:
            return api_key
        
        # Check query parameter (not recommended for production, but useful for testing)
        return request.GET.get('api_key')
    
    def is_valid_api_key(self, api_key: str) -> bool:
        """Validate API key against configured keys"""
        if not api_key:
            return False
        
        # Get configured API keys from settings
        valid_keys = getattr(settings, 'MNEMOSYNE_API_KEYS', [])
        if not valid_keys:
            return True  # No API keys configured = no authentication required
        
        return api_key in valid_keys
    
    def check_api_auth(self, request) -> Optional[HttpResponse]:
        """
        Check API authentication. Returns error response if authentication fails.
        Returns None if authentication passes.
        """
        api_key = self.get_api_key_from_request(request)
        
        if not self.is_valid_api_key(api_key):
            return HttpResponse(
                '{"success": false, "error": "Invalid or missing API key"}',
                content_type='application/json',
                status=401
            )
        
        return None


def generate_api_key() -> str:
    """Generate a secure API key for DIY setup"""
    import secrets
    return secrets.token_urlsafe(32)


def hash_password_simple(password: str, salt: str = None) -> tuple[str, str]:
    """
    Simple password hashing for basic authentication.
    Returns (hashed_password, salt)
    """
    if salt is None:
        import secrets
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 with SHA256 (built into Python)
    import hashlib
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return hashed.hex(), salt


def verify_password_simple(password: str, hashed_password: str, salt: str) -> bool:
    """Verify password against hash"""
    test_hash, _ = hash_password_simple(password, salt)
    return hmac.compare_digest(test_hash, hashed_password)


class RequestLoggingMixin:
    """
    Simple request logging for security monitoring.
    Logs suspicious activity patterns.
    """
    
    def log_security_event(self, request, event_type: str, details: str = ""):
        """Log security-related events"""
        import logging
        
        logger = logging.getLogger('mnemosyne.security')
        
        client_ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        
        logger.warning(
            f"Security Event [{event_type}] - IP: {client_ip} - "
            f"Path: {request.path} - UA: {user_agent[:100]} - Details: {details}"
        )
    
    def get_client_ip(self, request):
        """Get client IP with proxy support"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip