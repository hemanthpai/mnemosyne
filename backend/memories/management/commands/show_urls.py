from django.core.management.base import BaseCommand
from django.urls import get_resolver


class Command(BaseCommand):
    help = "Show all registered URL patterns"

    def handle(self, *args, **options):
        resolver = get_resolver()

        def print_urls(patterns, prefix=""):
            for pattern in patterns:
                if hasattr(pattern, "pattern"):
                    # This is a URL pattern
                    full_pattern = prefix + str(pattern.pattern)
                    if hasattr(pattern, "callback") and pattern.callback:
                        view_name = pattern.callback.__name__
                        self.stdout.write(f"{full_pattern} -> {view_name}")
                    elif hasattr(pattern, "name") and pattern.name:
                        self.stdout.write(f"{full_pattern} -> {pattern.name}")
                    else:
                        self.stdout.write(f"{full_pattern}")

                elif hasattr(pattern, "url_patterns"):
                    # This is an include()
                    new_prefix = prefix + str(pattern.pattern)
                    self.stdout.write(f"\n--- {new_prefix} ---")
                    print_urls(pattern.url_patterns, new_prefix)

        self.stdout.write("All registered URL patterns:")
        print_urls(resolver.url_patterns)
