from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from business.services import backfill_metrics


class Command(BaseCommand):
    help = "Backfill business analytics for an inclusive date range (YYYY-MM-DD)."

    def add_arguments(self, parser):
        parser.add_argument("start_date", help="Start date (YYYY-MM-DD)")
        parser.add_argument("end_date", help="End date (YYYY-MM-DD)")

    def handle(self, *args, **options):
        try:
            start = datetime.fromisoformat(options["start_date"]).date()
            end = datetime.fromisoformat(options["end_date"]).date()
        except ValueError as exc:
            raise CommandError(f"Invalid date: {exc}") from exc

        if start > end:
            raise CommandError("start_date must be <= end_date")

        backfill_metrics(start, end)
        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled metrics from {start.isoformat()} to {end.isoformat()}"
            ))
