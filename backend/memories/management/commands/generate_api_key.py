"""
Management command to generate secure API keys for authentication.
"""

from django.core.management.base import BaseCommand
from memories.security import generate_api_key


class Command(BaseCommand):
    help = 'Generate a secure API key for authentication'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=1,
            help='Number of API keys to generate (default: 1)'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write(self.style.SUCCESS('Generated API Key(s):'))
        self.stdout.write('=' * 50)
        
        keys = []
        for i in range(count):
            api_key = generate_api_key()
            keys.append(api_key)
            self.stdout.write(f"{i+1}. {api_key}")
        
        self.stdout.write('')
        self.stdout.write('To use these API keys:')
        self.stdout.write('1. Add them to your .env file:')
        self.stdout.write(f'   MNEMOSYNE_API_KEYS={",".join(keys)}')
        self.stdout.write('')
        self.stdout.write('2. Include the API key in requests as:')
        self.stdout.write('   - Header: "X-API-Key: <your_key>"')
        self.stdout.write('   - Header: "Authorization: Bearer <your_key>"')
        self.stdout.write('   - Query param: "?api_key=<your_key>" (testing only)')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Keep these keys secure and never commit them to version control!'))