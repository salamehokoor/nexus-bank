# business/tasks.py
from celery import shared_task

from .services import (
    compute_daily_business_metrics,
    compute_weekly_summary,
    compute_monthly_summary,
    compute_country_snapshot,
)


@shared_task(name="business.tasks.task_daily_metrics")
def task_daily_metrics():
    """
    Recompute today's DailyBusinessMetrics + Country snapshot.
    Safe to call many times per day.
    """
    compute_daily_business_metrics()
    compute_country_snapshot()


@shared_task(name="business.tasks.task_weekly_summary")
def task_weekly_summary():
    """
    Aggregate last week → WeeklySummary.
    """
    compute_weekly_summary()


@shared_task(name="business.tasks.task_monthly_summary")
def task_monthly_summary():
    """
    Aggregate current month → MonthlySummary.
    """
    compute_monthly_summary()
