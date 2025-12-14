from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Historical backfills are disabled; metrics are updated inline via signals."

    def handle(self, *args, **options):
        raise CommandError(
            "Backfill is no longer supported because metrics update in real time.")
