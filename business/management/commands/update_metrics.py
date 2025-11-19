from django.core.management.base import BaseCommand
from business.services import compute_daily_business_metrics, compute_country_snapshot


class Command(BaseCommand):
    help = "Update daily business analytics"

    def handle(self, *args, **kwargs):
        compute_daily_business_metrics()
        compute_country_snapshot()
        self.stdout.write(
            self.style.SUCCESS("Daily metrics updated successfully"))
