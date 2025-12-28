"""
Comprehensive edge case tests identified during codebase audit.
These tests verify potential failure scenarios without modifying existing logic.

Audit Date: 2025-12-28
"""

from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase, APIRequestFactory
from rest_framework import status

from api.models import Account, Card, Transaction, Biller, BillPayment
from api.serializers import (
    AccountSerializer,
    InternalTransferSerializer,
    ExternalTransferSerializer,
)
from api.convert_currency import jod_to_usd, usd_to_jod, jod_to_eur, eur_to_jod
from business.models import DailyBusinessMetrics
from risk.models import Incident, LoginEvent
from risk.utils import _get_ip_from_request, get_country_from_ip, _is_public_ip


User = get_user_model()


# =============================================================================
# API Module Edge Cases
# =============================================================================

class AccountTypeLimitsTests(TestCase):
    """H1: Test maximum_withdrawal_amount for all account types."""

    def setUp(self):
        self.user = User.objects.create_user(email="limits@test.com", password="x")

    def test_savings_account_has_limit(self):
        """Savings account should have defined withdrawal limit."""
        acc = Account.objects.create(
            user=self.user, type=Account.AccountTypes.SAVINGS
        )
        self.assertEqual(acc.maximum_withdrawal_amount, Decimal("10000.00"))

    def test_salary_account_has_limit(self):
        """Salary account should have defined withdrawal limit."""
        acc = Account.objects.create(
            user=self.user, type=Account.AccountTypes.SALARY
        )
        self.assertEqual(acc.maximum_withdrawal_amount, Decimal("10000.00"))

    def test_basic_account_has_limit(self):
        """Basic account should have defined withdrawal limit."""
        acc = Account.objects.create(
            user=self.user, type=Account.AccountTypes.BASIC
        )
        self.assertEqual(acc.maximum_withdrawal_amount, Decimal("10000.00"))

    def test_usd_account_type_has_limit(self):
        """
        USD account type now has a limit defined in LIMITS dict.
        This verifies the H1 fix.
        """
        acc = Account.objects.create(
            user=self.user, type=Account.AccountTypes.USD
        )
        self.assertEqual(acc.maximum_withdrawal_amount, Decimal("10000.00"))

    def test_eur_account_type_has_limit(self):
        """
        EUR account type now has a limit defined in LIMITS dict.
        This verifies the H1 fix.
        """
        acc = Account.objects.create(
            user=self.user, type=Account.AccountTypes.EUR
        )
        self.assertEqual(acc.maximum_withdrawal_amount, Decimal("10000.00"))


class FXConversionTests(TestCase):
    """M1: Test all FX conversion paths including unsupported pairs."""

    def setUp(self):
        self.user = User.objects.create_user(email="fx@test.com", password="x")

    def test_jod_to_usd_conversion(self):
        """JOD to USD conversion uses correct rate."""
        result = jod_to_usd(Decimal("100.00"))
        self.assertEqual(result, Decimal("141.00"))  # 100 * 1.41

    def test_usd_to_jod_conversion(self):
        """USD to JOD conversion uses correct rate."""
        result = usd_to_jod(Decimal("141.00"))
        self.assertEqual(result, Decimal("100.00"))  # 141 / 1.41

    def test_jod_to_eur_conversion(self):
        """JOD to EUR conversion uses correct rate."""
        result = jod_to_eur(Decimal("100.00"))
        self.assertEqual(result, Decimal("131.00"))  # 100 * 1.31

    def test_eur_to_jod_conversion(self):
        """EUR to JOD conversion uses correct rate."""
        result = eur_to_jod(Decimal("131.00"))
        self.assertEqual(result, Decimal("100.00"))  # 131 / 1.31

    def test_usd_to_eur_now_supported(self):
        """
        USD to EUR conversion IS now implemented via JOD intermediary.
        This verifies the M1 fix.
        """
        sender = Account.objects.create(
            user=self.user, balance=Decimal("1000.00"), currency="USD"
        )
        receiver = Account.objects.create(
            user=self.user, balance=Decimal("0.00"), currency="EUR"
        )
        # Should NOT raise anymore
        tx = Transaction.objects.create(
            sender_account=sender,
            receiver_account=receiver,
            amount=Decimal("100.00"),
        )
        self.assertEqual(tx.status, Transaction.Status.SUCCESS)

    def test_eur_to_usd_now_supported(self):
        """EUR to USD conversion IS now implemented via JOD intermediary."""
        sender = Account.objects.create(
            user=self.user, balance=Decimal("1000.00"), currency="EUR"
        )
        receiver = Account.objects.create(
            user=self.user, balance=Decimal("0.00"), currency="USD"
        )
        # Should NOT raise anymore
        tx = Transaction.objects.create(
            sender_account=sender,
            receiver_account=receiver,
            amount=Decimal("100.00"),
        )
        self.assertEqual(tx.status, Transaction.Status.SUCCESS)


class BillPaymentEdgeCases(TransactionTestCase):
    """M6: Test bill payment with missing system account."""

    def setUp(self):
        self.user = User.objects.create_user(email="bill@test.com", password="x")
        self.account = Account.objects.create(
            user=self.user, balance=Decimal("100.00")
        )
        # Biller WITHOUT system_account
        self.biller_no_system = Biller.objects.create(
            name="NullBiller",
            category="Other",
            fixed_amount=Decimal("50.00"),
            system_account=None,
        )

    def test_bill_payment_no_system_account_raises(self):
        """BillPayment.pay() should raise when biller has no system_account."""
        bill = BillPayment.objects.create(
            user=self.user,
            account=self.account,
            biller=self.biller_no_system,
            reference_number="REF-NOSYS-001",
        )
        with self.assertRaisesMessage(
            ValueError, "NullBiller has no system account"
        ):
            bill.pay()


class IdempotencyTests(TransactionTestCase):
    """Verify idempotency key handling prevents duplicate transactions."""

    def setUp(self):
        self.user = User.objects.create_user(email="idem@test.com", password="x")
        self.a1 = Account.objects.create(
            user=self.user, balance=Decimal("500.00")
        )
        self.a2 = Account.objects.create(
            user=self.user, balance=Decimal("0.00")
        )

    def test_duplicate_idempotency_key_returns_same_transaction(self):
        """Same idempotency_key should return existing transaction."""
        factory = APIRequestFactory()
        request = factory.post("/api/transfers/internal/")
        request.user = self.user

        data = {
            "sender_account": str(self.a1.account_number),
            "receiver_account": str(self.a2.account_number),
            "amount": "50.00",
            "idempotency_key": "unique-key-123",
        }

        # First request
        serializer1 = InternalTransferSerializer(
            data=data, context={"request": request}
        )
        serializer1.is_valid(raise_exception=True)
        tx1 = serializer1.save()

        # Second request with same key
        serializer2 = InternalTransferSerializer(
            data=data, context={"request": request}
        )
        serializer2.is_valid(raise_exception=True)
        tx2 = serializer2.save()

        self.assertEqual(tx1.pk, tx2.pk)
        self.assertEqual(
            Transaction.objects.filter(idempotency_key="unique-key-123").count(),
            1,
        )

    def test_null_idempotency_key_creates_new_transaction(self):
        """Null/blank idempotency_key should create new transactions."""
        factory = APIRequestFactory()
        request = factory.post("/api/transfers/internal/")
        request.user = self.user

        data = {
            "sender_account": str(self.a1.account_number),
            "receiver_account": str(self.a2.account_number),
            "amount": "10.00",
            "idempotency_key": "",
        }

        serializer1 = InternalTransferSerializer(
            data=data, context={"request": request}
        )
        serializer1.is_valid(raise_exception=True)
        tx1 = serializer1.save()

        serializer2 = InternalTransferSerializer(
            data=data, context={"request": request}
        )
        serializer2.is_valid(raise_exception=True)
        tx2 = serializer2.save()

        self.assertNotEqual(tx1.pk, tx2.pk)


# =============================================================================
# Risk Module Edge Cases
# =============================================================================

class IPUtilityTests(TestCase):
    """Test IP extraction and country lookup utilities."""

    def test_get_ip_from_xff_header(self):
        """XFF header should be preferred over REMOTE_ADDR."""
        request = MagicMock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8",
            "REMOTE_ADDR": "192.168.1.1",
        }
        ip = _get_ip_from_request(request)
        self.assertEqual(ip, "1.2.3.4")

    def test_get_ip_from_remote_addr(self):
        """Falls back to REMOTE_ADDR when XFF is absent."""
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}
        ip = _get_ip_from_request(request)
        self.assertEqual(ip, "10.0.0.1")

    def test_get_ip_from_none_request(self):
        """Returns None for None request."""
        ip = _get_ip_from_request(None)
        self.assertIsNone(ip)

    def test_is_public_ip_private(self):
        """Private IPs should not be considered public."""
        self.assertFalse(_is_public_ip("192.168.1.1"))
        self.assertFalse(_is_public_ip("10.0.0.1"))
        self.assertFalse(_is_public_ip("172.16.0.1"))

    def test_is_public_ip_loopback(self):
        """Loopback IPs should not be considered public."""
        self.assertFalse(_is_public_ip("127.0.0.1"))

    def test_is_public_ip_valid_public(self):
        """Valid public IPs should be recognized."""
        self.assertTrue(_is_public_ip("8.8.8.8"))
        self.assertTrue(_is_public_ip("1.1.1.1"))

    def test_is_public_ip_invalid(self):
        """Invalid IPs should return False."""
        self.assertFalse(_is_public_ip("not-an-ip"))
        self.assertFalse(_is_public_ip(""))


class LoginEventTests(TransactionTestCase):
    """Test login event recording and incident creation."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="login@test.com", password="testpass"
        )

    def test_successful_login_creates_event(self):
        """Successful login should create LoginEvent with successful=True."""
        event = LoginEvent.objects.create(
            user=self.user,
            ip="1.2.3.4",
            country="US",
            successful=True,
            attempted_email="login@test.com",
            source="password",
        )
        self.assertTrue(event.successful)
        self.assertEqual(str(event), "[OK] login@test.com @ 1.2.3.4")

    def test_failed_login_creates_event(self):
        """Failed login should create LoginEvent with successful=False."""
        event = LoginEvent.objects.create(
            user=None,
            ip="5.6.7.8",
            country="RU",
            successful=False,
            attempted_email="unknown@test.com",
            source="password",
            failure_reason="invalid_credentials",
        )
        self.assertFalse(event.successful)
        self.assertIn("FAIL", str(event))


class IncidentCreationTests(TestCase):
    """Test incident model and severity levels."""

    def test_incident_severity_choices(self):
        """All severity levels should be valid."""
        user = User.objects.create_user(email="inc@test.com", password="x")
        
        for severity, _ in Incident.SEVERITY_CHOICES:
            incident = Incident.objects.create(
                user=user,
                event=f"Test {severity}",
                severity=severity,
            )
            self.assertEqual(incident.severity, severity)

    def test_incident_str_representation(self):
        """Incident __str__ should include event and severity."""
        incident = Incident.objects.create(
            user=None,
            event="Test Event",
            severity="high",
        )
        self.assertIn("Test Event", str(incident))
        self.assertIn("high", str(incident))


# =============================================================================
# Business Module Edge Cases
# =============================================================================

class MetricsUpdateTests(TransactionTestCase):
    """Test metrics update on transaction creation."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="metrics@test.com", password="x"
        )
        self.a1 = Account.objects.create(
            user=self.user, balance=Decimal("1000.00"), currency="JOD"
        )
        self.a2 = Account.objects.create(
            user=self.user, balance=Decimal("0.00"), currency="JOD"
        )

    def _today_metrics(self):
        return DailyBusinessMetrics.objects.filter(
            date=timezone.localdate()
        ).first()

    def test_transaction_increments_success_count(self):
        """Successful transaction should increment success counter."""
        Transaction.objects.create(
            sender_account=self.a1,
            receiver_account=self.a2,
            amount=Decimal("100.00"),
            status=Transaction.Status.SUCCESS,
        )
        metrics = self._today_metrics()
        self.assertIsNotNone(metrics)
        self.assertGreaterEqual(metrics.total_transactions_success, 1)

    def test_transaction_increments_transferred_amount(self):
        """Successful transaction should add to total_transferred_amount."""
        Transaction.objects.create(
            sender_account=self.a1,
            receiver_account=self.a2,
            amount=Decimal("50.00"),
            status=Transaction.Status.SUCCESS,
        )
        metrics = self._today_metrics()
        self.assertIsNotNone(metrics)
        self.assertGreaterEqual(metrics.total_transferred_amount, Decimal("50.00"))


# =============================================================================
# API Endpoint Tests
# =============================================================================

class ExternalTransferAPITests(APITestCase):
    """Test external transfer endpoint with correct payload structure."""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(
            email="ext1@test.com", password="x"
        )
        self.user2 = User.objects.create_user(
            email="ext2@test.com", password="x"
        )
        self.sender = Account.objects.create(
            user=self.user1, balance=Decimal("500.00")
        )
        self.receiver = Account.objects.create(
            user=self.user2, balance=Decimal("0.00")
        )

    def test_external_transfer_uses_receiver_account_number(self):
        """API expects receiver_account_number, not receiver_account."""
        self.client.force_authenticate(user=self.user1)
        
        # Correct payload structure
        payload = {
            "sender_account": str(self.sender.account_number),
            "receiver_account_number": str(self.receiver.account_number),
            "amount": "100.00",
        }
        response = self.client.post(
            "/transfers/external/", payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_external_transfer_wrong_field_rejected(self):
        """Using receiver_account instead of receiver_account_number fails."""
        self.client.force_authenticate(user=self.user1)
        
        # Wrong payload structure (using receiver_account)
        payload = {
            "sender_account": str(self.sender.account_number),
            "receiver_account": str(self.receiver.account_number),  # Wrong field
            "amount": "100.00",
        }
        response = self.client.post(
            "/transfers/external/", payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OwnershipScopingTests(APITestCase):
    """Verify users can only access their own resources."""

    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(email="own1@test.com", password="x")
        self.user2 = User.objects.create_user(email="own2@test.com", password="x")
        self.acc1 = Account.objects.create(
            user=self.user1, balance=Decimal("100.00")
        )
        self.acc2 = Account.objects.create(
            user=self.user2, balance=Decimal("200.00")
        )

    def test_user_cannot_list_other_accounts(self):
        """User1 should not see User2's accounts."""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get("/accounts")
        
        account_numbers = [a["account_number"] for a in response.data]
        self.assertIn(self.acc1.account_number, account_numbers)
        self.assertNotIn(self.acc2.account_number, account_numbers)

    def test_user_cannot_send_from_other_account(self):
        """User cannot send from account they don't own."""
        self.client.force_authenticate(user=self.user1)
        
        payload = {
            "sender_account": str(self.acc2.account_number),  # Owned by user2
            "receiver_account": str(self.acc1.account_number),
            "amount": "10.00",
        }
        response = self.client.post(
            "/transfers/internal/", payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
