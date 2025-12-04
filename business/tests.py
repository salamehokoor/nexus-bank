from datetime import date, timedelta
from unittest import skip

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import DailyBusinessMetrics
from .services import compute_daily_business_metrics, backfill_metrics


class DailyMetricsComputationTests(TestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_daily_metrics_idempotent(self):
        target_date = timezone.localdate()
        compute_daily_business_metrics(target_date)
        compute_daily_business_metrics(target_date)
        self.assertEqual(
            DailyBusinessMetrics.objects.filter(date=target_date).count(), 1)

    def test_backfill_creates_rows(self):
        start = date.today() - timedelta(days=1)
        end = date.today()
        backfill_metrics(start, end)
        self.assertTrue(
            DailyBusinessMetrics.objects.filter(date__gte=start,
                                                date__lte=end).exists())


@skip("Integration tests require fixtures for api/risk apps.")
class IntegrationMetricFlowTests(TestCase):
    def test_placeholder(self):
        self.assertTrue(True)
