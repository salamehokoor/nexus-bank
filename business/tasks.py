from celery import shared_task
from .services import (
    compute_daily_business_metrics,
    compute_weekly_summary,
    compute_monthly_summary,
    compute_country_snapshot,
)


@shared_task
def task_daily_metrics():
    compute_daily_business_metrics()
    compute_country_snapshot()


@shared_task
def task_weekly_summary():
    compute_weekly_summary()


@shared_task
def task_monthly_summary():
    compute_monthly_summary()
