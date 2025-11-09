"""
Django management command to set up scheduled tasks

Usage:
    python manage.py setup_schedules
"""

from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = 'Set up scheduled tasks for Mnemosyne'

    def handle(self, *args, **options):
        """Create scheduled tasks for background processing"""

        # Nightly relationship building (2am every day)
        schedule, created = Schedule.objects.update_or_create(
            name='nightly_relationship_building',
            defaults={
                'func': 'memories.tasks.nightly_relationship_building_all_users',
                'schedule_type': Schedule.CRON,
                'cron': '0 2 * * *',  # 2am daily
                'repeats': -1,  # Repeat indefinitely
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created nightly relationship building schedule'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Updated nightly relationship building schedule'))

        self.stdout.write(self.style.SUCCESS('\nScheduled tasks:'))
        self.stdout.write(f'  - Nightly relationship building: 2am daily (all users)')
