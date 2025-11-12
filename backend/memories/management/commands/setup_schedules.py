"""
Django management command to set up scheduled tasks

Usage:
    python manage.py setup_schedules

Note: Currently no scheduled tasks are configured.
Relationship building and memory evolution happen inline during extraction.
"""

from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = 'Set up scheduled tasks for Mnemosyne'

    def handle(self, *args, **options):
        """Create scheduled tasks for background processing"""

        # Clean up old nightly relationship building schedule if it exists
        deleted_count, _ = Schedule.objects.filter(name='nightly_relationship_building').delete()

        if deleted_count > 0:
            self.stdout.write(self.style.SUCCESS('✓ Removed old nightly relationship building schedule'))
            self.stdout.write(self.style.WARNING('  (Relationships now built inline during extraction)'))

        self.stdout.write(self.style.SUCCESS('\nScheduled tasks:'))
        self.stdout.write('  - None currently configured')
        self.stdout.write('  - Relationship building: Inline during extraction')
        self.stdout.write('  - Memory evolution: Inline during extraction')
