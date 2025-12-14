from datetime import date, timedelta
from unittest import skip

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (ActiveUserWindow, CountryUserMetrics, CurrencyMetrics,
                     DailyBusinessMetrics, MonthlySummary, WeeklySummary)
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


class BusinessApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="biz@example.com", password="testpass123")
        self.client.force_authenticate(self.user)

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        DailyBusinessMetrics.objects.create(date=today)
        WeeklySummary.objects.create(week_start=week_start, week_end=today)
        MonthlySummary.objects.create(month=month_start)
        CountryUserMetrics.objects.create(date=today,
                                          country="US",
                                          count=5,
                                          active_users=3,
                                          tx_count=1)
        CurrencyMetrics.objects.create(date=today,
                                       currency="USD",
                                       tx_count=1)
        ActiveUserWindow.objects.create(date=today,
                                        window="dau",
                                        active_users=7)

    def test_business_endpoints_succeed_without_pagination_params(self):
        endpoints = [
            "/business/weekly/",
            "/business/monthly/",
            "/business/countries/",
            "/business/currencies/",
            "/business/active/",
        ]
        for url in endpoints:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(len(resp.data) >= 1)

    def test_daily_and_overview_endpoints(self):
        daily_resp = self.client.get("/business/daily/")
        self.assertEqual(daily_resp.status_code, 200)
        self.assertIn("date", daily_resp.data)

        overview_resp = self.client.get("/business/overview/")
        self.assertEqual(overview_resp.status_code, 200)
        # Overview should include each section without errors
        for key in ("daily", "weekly", "monthly", "country", "currency",
                    "active"):
            self.assertIn(key, overview_resp.data)
