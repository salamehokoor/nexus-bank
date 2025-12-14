from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Manual recompute is disabled; metrics update inline via signals."

    def handle(self, *args, **kwargs):
        raise CommandError(
            "Real-time metrics are maintained automatically; no manual recompute needed."
        )
