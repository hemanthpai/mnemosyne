"""
Management command to view rate limiting statistics and test rate limits.
"""

from django.core.management.base import BaseCommand
from memories.rate_limiter import rate_limiter


class Command(BaseCommand):
    help = 'View rate limiting statistics and configuration'

    def handle(self, *args, **options):
        stats = rate_limiter.get_stats()
        
        self.stdout.write(self.style.SUCCESS('Rate Limiting Statistics'))
        self.stdout.write('=' * 40)
        self.stdout.write(f"Active IP addresses: {stats['active_ips']}")
        self.stdout.write(f"Total recent requests: {stats['total_recent_requests']}")
        self.stdout.write('')
        self.stdout.write('Rate Limits:')
        self.stdout.write(f"  Memory extraction: {stats['extract_limit']} requests/minute")
        self.stdout.write(f"  Memory retrieval: {stats['retrieve_limit']} requests/minute")
        self.stdout.write(f"  Window size: {stats['window_size_seconds']} seconds")
        self.stdout.write('')
        
        if stats['active_ips'] > 0:
            self.stdout.write('Recent activity detected.')
        else:
            self.stdout.write('No recent activity.')