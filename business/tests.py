from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from api.models import Account, BillPayment, Biller, Transaction
from api.serializers import InternalTransferSerializer
from business.models import DailyBusinessMetrics


class MetricsSignalTests(TransactionTestCase):

    def setUp(self):
        self.User = get_user_model()
        self.user1 = self.User.objects.create_user(email="u1@example.com",
                                                   password="pass")
        self.user2 = self.User.objects.create_user(email="u2@example.com",
                                                   password="pass")
        self.a1 = Account.objects.create(user=self.user1,
                                         balance=Decimal("200.00"),
                                         currency="JOD")
        self.a2 = Account.objects.create(user=self.user2,
                                         balance=Decimal("50.00"),
                                         currency="JOD")
        self.a3 = Account.objects.create(user=self.user1,
                                         balance=Decimal("80.00"),
                                         currency="JOD")

    def _today_metrics(self):
        return DailyBusinessMetrics.objects.get(date=timezone.localdate())

    def test_transaction_updates_metrics_incrementally(self):
        tx = Transaction.objects.create(sender_account=self.a1,
                                        receiver_account=self.a2,
                                        amount=Decimal("25.00"),
                                        fee_amount=Decimal("1.50"),
                                        status=Transaction.Status.SUCCESS)
        metrics = self._today_metrics()
        self.assertEqual(metrics.total_transactions_success, 1)
        self.assertEqual(metrics.total_transferred_amount,
                         Decimal("25.00"))
        self.assertEqual(metrics.fee_revenue, Decimal("1.50"))
        self.assertEqual(metrics.net_revenue, Decimal("1.50"))
        self.assertEqual(tx.status, Transaction.Status.SUCCESS)

    def test_bill_payment_settles_and_updates_metrics(self):
        system_account = Account.objects.create(user=self.user1,
                                                balance=Decimal("0.00"),
                                                currency="JOD")
        biller = Biller.objects.create(name="WaterCo",
                                       category="Water",
                                       fixed_amount=Decimal("30.00"),
                                       system_account=system_account)
        bill_payment = BillPayment.objects.create(user=self.user1,
                                                  account=self.a1,
                                                  biller=biller,
                                                  reference_number="REF123")
        bill_payment.pay()
        bill_payment.refresh_from_db()
        self.assertEqual(bill_payment.status, "PAID")
        metrics = self._today_metrics()
        self.assertEqual(metrics.bill_payments_count, 1)
        self.assertEqual(metrics.bill_payments_amount, Decimal("30.00"))

    def test_idempotent_transaction_creation(self):
        factory = APIRequestFactory()
        request = factory.post("/api/transfers/internal/")
        request.user = self.user1
        serializer = InternalTransferSerializer(
            data={
                "sender_account": str(self.a1.account_number),
                "receiver_account": str(self.a3.account_number),
                "amount": "10.00",
                "idempotency_key": "dupe-key",
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        tx1 = serializer.save()
        serializer = InternalTransferSerializer(
            data={
                "sender_account": str(self.a1.account_number),
                "receiver_account": str(self.a3.account_number),
                "amount": "10.00",
                "idempotency_key": "dupe-key",
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        tx2 = serializer.save()

        self.assertEqual(tx1.pk, tx2.pk)
        self.assertEqual(
            Transaction.objects.filter(idempotency_key="dupe-key").count(), 1)
        metrics = self._today_metrics()
        self.assertEqual(metrics.total_transactions_success, 1)
        self.a1.refresh_from_db()
        self.a3.refresh_from_db()
        self.assertEqual(self.a1.balance, Decimal("190.00"))
        self.assertEqual(self.a3.balance, Decimal("90.00"))


class AIBusinessAdvisorTests(TransactionTestCase):
    """
    Tests for the AI Business Advisor endpoint.

    These tests verify:
    - Missing API key returns 200 with null ai_analysis
    - Persistence of insights works correctly
    - Admin-only access control
    """

    def setUp(self):
        self.User = get_user_model()
        # Use a specific test date to avoid conflicts
        self.test_date = date(2025, 6, 15)
        # Create admin user
        self.admin_user = self.User.objects.create_user(
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
            is_superuser=True,
        )
        # Create regular user
        self.regular_user = self.User.objects.create_user(
            email="user@example.com",
            password="userpass",
        )
        # Create some metrics data - use get_or_create to avoid conflicts
        DailyBusinessMetrics.objects.get_or_create(
            date=self.test_date,
            defaults={
                "new_users": 10,
                "total_users": 100,
                "active_users": 50,
                "total_transactions_success": 25,
                "total_transactions_failed": 2,
                "fee_revenue": Decimal("50.00"),
                "net_revenue": Decimal("50.00"),
                "profit": Decimal("50.00"),
            }
        )


    def test_missing_api_key_returns_200_with_null_analysis(self):
        """
        When GEMINI_API_KEY is missing, endpoint returns 200 with ai_analysis=null.
        """
        from django.test import override_settings
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        with override_settings(GEMINI_API_KEY=None):
            response = client.post(
                "/business/ai/advisor/",
                {"period_type": "daily", "date": str(self.test_date)},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data.get("ai_analysis"))
        self.assertIn("report_text", response.data)
        self.assertIn("report_json", response.data)

    def test_persistence_creates_daily_insight(self):
        """
        The endpoint should create/update DailyAIInsight records.
        """
        from django.test import override_settings
        from rest_framework.test import APIClient
        from business.models import DailyAIInsight

        client = APIClient()
        client.force_authenticate(user=self.admin_user)

        with override_settings(GEMINI_API_KEY=None):
            response = client.post(
                "/business/ai/advisor/",
                {"period_type": "daily", "date": str(self.test_date)},
                format="json",
            )

        self.assertEqual(response.status_code, 200)

        # Check persistence
        insight = DailyAIInsight.objects.filter(date=self.test_date).first()
        self.assertIsNotNone(insight)
        self.assertIsNone(insight.ai_output)  # No API key
        self.assertEqual(insight.model_name, "gemini-2.5-flash")
        self.assertIn("NEXUS BANK", insight.report_text)

    def test_admin_only_access(self):
        """
        Regular users should not be able to access the endpoint.
        """
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.regular_user)

        response = client.post(
            "/business/ai/advisor/",
            {"period_type": "daily", "date": str(self.test_date)},
            format="json",
        )

        # Should return 403 Forbidden for non-admin users
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_access_denied(self):
        """
        Unauthenticated requests should be denied.
        """
        from rest_framework.test import APIClient

        client = APIClient()

        response = client.post(
            "/business/ai/advisor/",
            {"period_type": "daily", "date": str(self.test_date)},
            format="json",
        )

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

