"""
Celery task wrappers for business metrics recomputation.
Tasks are idempotent and safe to run multiple times for the same window.
"""
from datetime import datetime, timedelta

from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone

from .services import (
    backfill_metrics,
    compute_daily_business_metrics,
    compute_weekly_summary,
    compute_monthly_summary,
    compute_country_snapshot,
)


def _parse_iso_date(value, default):
    """Parse ISO date string to date; return default on falsy/invalid."""
    if not value:
        return default
    return datetime.fromisoformat(value).date()


@shared_task(name="business.tasks.task_daily_metrics")
def task_daily_metrics(date=None):
    """
    Recompute a specific day's metrics. Safe to retry and run multiple times.

    Args:
        date: Optional ISO date string; defaults to today in local TZ.
    """
    target_date = _parse_iso_date(date, timezone.localdate())
    compute_daily_business_metrics(target_date)
    compute_country_snapshot(target_date)


@shared_task(name="business.tasks.task_weekly_summary")
def task_weekly_summary(week_start=None):
    """
    Aggregate the given week (Monday start). Safe to retry.

    Args:
        week_start: Optional ISO date string for Monday of target week.
    """
    today = timezone.localdate()
    week_start_date = _parse_iso_date(week_start,
                                      today - timedelta(days=today.weekday()))
    compute_weekly_summary(week_start_date)


@shared_task(name="business.tasks.task_monthly_summary")
def task_monthly_summary(month_start=None):
    """
    Aggregate the given month (first day). Safe to retry.

    Args:
        month_start: Optional ISO date string for first day of month.
    """
    today = timezone.localdate()
    month_start_date = _parse_iso_date(month_start, today.replace(day=1))
    compute_monthly_summary(month_start_date)


@shared_task(name="business.tasks.task_backfill_metrics")
def task_backfill_metrics(start_date, end_date):
    """
    Backfill a date range inclusively. Use for historical rebuilds.

    Args:
        start_date: ISO date string (inclusive).
        end_date: ISO date string (inclusive).

    Raises:
        ValueError: if either date is missing.
    """
    start = _parse_iso_date(start_date, None)
    end = _parse_iso_date(end_date, None)
    if not start or not end:
        raise ValueError("start_date and end_date are required")
    backfill_metrics(start, end)


# Suggested Celery beat schedule (place into settings.CELERY_BEAT_SCHEDULE)
CELERY_BEAT_SCHEDULE = {
    "business-daily-0005": {
        "task": "business.tasks.task_daily_metrics",
        "schedule": crontab(minute="5", hour="0"),
    },
    "business-weekly-mon-0010": {
        "task": "business.tasks.task_weekly_summary",
        "schedule": crontab(minute="10", hour="0", day_of_week="mon"),
    },
    "business-monthly-0015": {
        "task": "business.tasks.task_monthly_summary",
        "schedule": crontab(minute="15", hour="0", day_of_month="1"),
    },
    "business-daily-delta-refresh": {
        "task": "business.tasks.task_daily_metrics",
        "schedule": crontab(minute="*/30"),
    },
}
