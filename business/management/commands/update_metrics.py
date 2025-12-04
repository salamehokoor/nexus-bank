from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from business.services import (
    compute_daily_business_metrics,
    compute_weekly_summary,
    compute_monthly_summary,
    compute_country_snapshot,
)


class Command(BaseCommand):
    help = "Update business analytics (daily, weekly, monthly) for the provided dates or today."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            help="ISO date for daily metrics (default: today)",
        )
        parser.add_argument(
            "--week-start",
            dest="week_start",
            help="ISO date (Monday) for weekly summary (default: current week)",
        )
        parser.add_argument(
            "--month-start",
            dest="month_start",
            help="ISO date (first day) for monthly summary (default: current month)",
        )

    def handle(self, *args, **kwargs):
        today = timezone.localdate()
        date = kwargs.get("date")
        week_start = kwargs.get("week_start")
        month_start = kwargs.get("month_start")

        date_obj = datetime.fromisoformat(date).date() if date else today
        week_obj = datetime.fromisoformat(
            week_start).date() if week_start else today - timedelta(
                days=today.weekday())
        month_obj = datetime.fromisoformat(month_start).date(
        ) if month_start else today.replace(day=1)

        compute_daily_business_metrics(date_obj)
        compute_country_snapshot(date_obj)
        compute_weekly_summary(week_obj)
        compute_monthly_summary(month_obj)

        self.stdout.write(self.style.SUCCESS("Metrics updated successfully"))
