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
