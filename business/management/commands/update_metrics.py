from django.core.management.base import BaseCommand
from business.services import (compute_daily_business_metrics,
                               compute_country_snapshot,
                               compute_weekly_summary, compute_monthly_summary)


class Command(BaseCommand):
    help = "Update business analytics (daily, weekly, monthly)"

    def handle(self, *args, **kwargs):
        # Daily
        compute_daily_business_metrics()
        compute_country_snapshot()

        # Weekly
        compute_weekly_summary()

        # Monthly
        compute_monthly_summary()

        self.stdout.write(
            self.style.SUCCESS("All metrics updated successfully"))
