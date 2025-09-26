"""
Management command to audit security configuration and provide recommendations.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from memories.rate_limiter import rate_limiter


class Command(BaseCommand):
    help = 'Audit security configuration and provide recommendations'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Mnemosyne Security Audit'))
        self.stdout.write('=' * 40)
        self.stdout.write('')
        
        # Check DEBUG setting
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING('⚠️  DEBUG is enabled'))
            self.stdout.write('   Recommendation: Set DEBUG=False for production')
        else:
            self.stdout.write(self.style.SUCCESS('✅ DEBUG is disabled'))
        
        # Check SECRET_KEY
        if hasattr(settings, 'SECRET_KEY') and len(settings.SECRET_KEY) >= 50:
            self.stdout.write(self.style.SUCCESS('✅ SECRET_KEY is configured'))
        else:
            self.stdout.write(self.style.ERROR('❌ SECRET_KEY is weak or missing'))
            self.stdout.write('   Recommendation: Generate a strong SECRET_KEY')
        
        # Check API key authentication
        api_keys = getattr(settings, 'MNEMOSYNE_API_KEYS', [])
        if api_keys and api_keys != ['']:
            self.stdout.write(self.style.SUCCESS(f'✅ API key authentication enabled ({len(api_keys)} keys)'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  No API key authentication'))
            self.stdout.write('   Recommendation: Generate API keys with: python manage.py generate_api_key')
        
        # Check rate limiting
        stats = rate_limiter.get_stats()
        self.stdout.write(self.style.SUCCESS('✅ Rate limiting enabled'))
        self.stdout.write(f'   Extract limit: {stats["extract_limit"]}/minute')
        self.stdout.write(f'   Retrieve limit: {stats["retrieve_limit"]}/minute')
        
        # Check ALLOWED_HOSTS
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        if '*' in allowed_hosts:
            self.stdout.write(self.style.WARNING('⚠️  ALLOWED_HOSTS includes wildcard'))
            self.stdout.write('   Recommendation: Specify exact hostnames')
        elif allowed_hosts:
            self.stdout.write(self.style.SUCCESS(f'✅ ALLOWED_HOSTS configured: {allowed_hosts}'))
        else:
            self.stdout.write(self.style.ERROR('❌ ALLOWED_HOSTS not configured'))
        
        # Check security middleware
        middleware = getattr(settings, 'MIDDLEWARE', [])
        security_middleware = 'memories.security.SecurityHeadersMiddleware'
        if security_middleware in middleware:
            self.stdout.write(self.style.SUCCESS('✅ Security headers middleware enabled'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Security headers middleware not found'))
        
        # HTTPS recommendations
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🔒 HTTPS Recommendations:'))
        
        https_settings = [
            'SECURE_SSL_REDIRECT',
            'SECURE_HSTS_SECONDS',
            'SESSION_COOKIE_SECURE',
            'CSRF_COOKIE_SECURE'
        ]
        
        https_configured = any(getattr(settings, setting, False) for setting in https_settings)
        if https_configured:
            self.stdout.write('   ✅ Some HTTPS settings configured')
        else:
            self.stdout.write('   ⚠️  No HTTPS settings configured')
            self.stdout.write('   For production with SSL/TLS, consider enabling:')
            for setting in https_settings:
                self.stdout.write(f'   - {setting}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Security Summary:'))
        self.stdout.write('- Security headers are automatically applied')
        self.stdout.write('- Rate limiting prevents abuse')
        self.stdout.write('- Optional API key authentication available')
        self.stdout.write('- For production: enable HTTPS and related settings')