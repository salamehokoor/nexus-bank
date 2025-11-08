from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from datetime import date

from .models import Account, Card, Transaction
from .serializers import AccountSerializer, CardSerializer


class UserModelTests(TestCase):

    def test_create_user_and_superuser(self):
        User = get_user_model()
        user = User.objects.create_user(email="u1@example.com",
                                        password="pass123")
        self.assertTrue(user.check_password("pass123"))
        self.assertEqual(user.email, "u1@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(str(user), user.email)

        su = User.objects.create_superuser(email="admin@example.com",
                                           password="adm1n")
        self.assertTrue(su.is_staff)
        self.assertTrue(su.is_superuser)


class AccountModelTests(TestCase):

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="acc@example.com",
                                                  password="x")

    def test_defaults_and_str(self):
        acc = Account.objects.create(user=self.user)
        self.assertIsNotNone(acc.id)
        self.assertEqual(len(acc.account_number), 12)
        self.assertEqual(str(acc), acc.account_number)
        self.assertEqual(acc.balance, Decimal("0.00"))

    def test_maximum_withdrawal_amount_by_type(self):
        acc = Account.objects.create(user=self.user,
                                     type=Account.AccountTypes.SAVINGS)
        self.assertEqual(acc.maximum_withdrawal_amount,
                         Account.LIMITS[Account.AccountTypes.SAVINGS])

    def test_balance_nonnegative_constraint(self):
        # Check constraint should prevent negative balances
        with self.assertRaises(IntegrityError):
            Account.objects.create(user=self.user, balance=Decimal("-1.00"))


class CardModelTests(TestCase):

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="card@example.com",
                                                  password="x")
        self.acc = Account.objects.create(user=self.user)

    def test_auto_generated_fields_and_str(self):
        card = Card.objects.create(account=self.acc)
        self.assertEqual(len(card.card_number), 16)
        self.assertEqual(len(card.cvv), 3)
        # expiration_date may be a datetime per model default; normalize to date
        exp = card.expiration_date.date() if hasattr(
            card.expiration_date, "date") else card.expiration_date
        self.assertTrue(isinstance(exp, date))
        self.assertGreater(exp, date.today())
        self.assertEqual(str(card), card.card_number)


class TransactionModelTests(TestCase):

    def setUp(self):
        self.User = get_user_model()
        self.user1 = self.User.objects.create_user(email="t1@example.com",
                                                   password="x")
        self.user2 = self.User.objects.create_user(email="t2@example.com",
                                                   password="x")
        self.a1 = Account.objects.create(user=self.user1,
                                         balance=Decimal("100.00"))
        self.a2 = Account.objects.create(user=self.user2,
                                         balance=Decimal("50.00"))

    def test_successful_transfer_and_snapshots(self):
        tx = Transaction.objects.create(sender_account=self.a1,
                                        receiver_account=self.a2,
                                        amount=Decimal("40.00"))
        self.a1.refresh_from_db()
        self.a2.refresh_from_db()
        self.assertEqual(self.a1.balance, Decimal("60.00"))
        self.assertEqual(self.a2.balance, Decimal("90.00"))
        self.assertEqual(tx.sender_balance_after, Decimal("60.00"))
        self.assertEqual(tx.receiver_balance_after, Decimal("90.00"))

    def test_cannot_transfer_to_same_account(self):
        with self.assertRaisesMessage(ValueError,
                                      "Cannot transfer to the same account."):
            Transaction.objects.create(sender_account=self.a1,
                                       receiver_account=self.a1,
                                       amount=Decimal("1.00"))

    def test_amount_must_be_positive(self):
        with self.assertRaisesMessage(ValueError, "Amount must be positive."):
            Transaction.objects.create(sender_account=self.a1,
                                       receiver_account=self.a2,
                                       amount=Decimal("0.00"))

    def test_insufficient_funds(self):
        with self.assertRaisesMessage(ValueError, "Insufficient funds."):
            Transaction.objects.create(sender_account=self.a2,
                                       receiver_account=self.a1,
                                       amount=Decimal("100.00"))


class SerializerTests(TestCase):

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(email="ser@example.com",
                                                  password="x",
                                                  first_name="Ann")
        self.acc = Account.objects.create(user=self.user,
                                          balance=Decimal("123.45"))
        self.card = Card.objects.create(account=self.acc)

    def test_account_serializer_fields(self):
        data = AccountSerializer(self.acc).data
        self.assertEqual(data["id"], str(self.acc.id))
        self.assertEqual(data["account_number"], self.acc.account_number)
        self.assertEqual(data["owner"]["email"], self.user.email)
        self.assertIn("mask", data)
        self.assertTrue(data["mask"].endswith(self.acc.account_number[-4:]))
        self.assertEqual(Decimal(str(data["maximum_withdrawal_amount"])),
                         self.acc.maximum_withdrawal_amount)
        self.assertEqual(data["card_count"], 1)

    def test_card_serializer_fields(self):
        data = CardSerializer(self.card).data
        self.assertEqual(data["card_type"], self.card.card_type)
        self.assertEqual(data["last4"], self.card.card_number[-4:])
        self.assertIn("expiration_date", data)
        # ISO format string (YYYY-MM-DD)
        self.assertRegex(data["expiration_date"], r"^\d{4}-\d{2}-\d{2}$")


class AccountsAPITests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()
        self.u1 = self.User.objects.create_user(email="api1@example.com",
                                                password="x")
        self.u2 = self.User.objects.create_user(email="api2@example.com",
                                                password="x")
        # Accounts for u1
        self.a1 = Account.objects.create(user=self.u1,
                                         balance=Decimal("50.00"),
                                         type=Account.AccountTypes.SAVINGS)
        self.a2 = Account.objects.create(user=self.u1,
                                         balance=Decimal("150.00"),
                                         type=Account.AccountTypes.BASIC)
        # Account for u2
        self.b1 = Account.objects.create(user=self.u2,
                                         balance=Decimal("300.00"))

    def test_auth_required(self):
        url = reverse("accounts-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_only_current_user_accounts(self):
        self.client.force_authenticate(user=self.u1)
        url = reverse("accounts-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Should not include u2's account
        returned_ids = {item["id"] for item in res.data}
        self.assertIn(str(self.a1.id), returned_ids)
        self.assertIn(str(self.a2.id), returned_ids)
        self.assertNotIn(str(self.b1.id), returned_ids)

    def test_filter_by_type(self):
        self.client.force_authenticate(user=self.u1)
        url = reverse("accounts-list")
        res = self.client.get(url, {"type": Account.AccountTypes.SAVINGS})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["id"], str(self.a1.id))

    def test_ordering_by_balance_desc(self):
        self.client.force_authenticate(user=self.u1)
        url = reverse("accounts-list")
        res = self.client.get(url, {"ordering": "-balance"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 2)
        self.assertEqual(res.data[0]["id"],
                         str(self.a2.id))  # highest balance first

    def test_create_account_ignores_user_in_payload(self):
        self.client.force_authenticate(user=self.u1)
        url = reverse("accounts-list")
        payload = {
            "type": Account.AccountTypes.SALARY,
            "balance": "77.50",
            "user": str(self.u2.id),  # should be ignored by the view
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created_id = res.data["id"]
        acc = Account.objects.get(id=created_id)
        self.assertEqual(acc.user, self.u1)
        self.assertEqual(acc.balance, Decimal("77.50"))


class AccountCardsAPITests(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()
        self.owner = self.User.objects.create_user(email="owner@example.com",
                                                   password="x")
        self.other = self.User.objects.create_user(email="other@example.com",
                                                   password="x")
        self.acc = Account.objects.create(user=self.owner)
        self.other_acc = Account.objects.create(user=self.other)

    def test_list_cards_requires_ownership(self):
        # add a couple of cards
        Card.objects.create(account=self.acc)
        Card.objects.create(account=self.acc)

        # owner can list
        self.client.force_authenticate(user=self.owner)
        url = reverse("account-cards", kwargs={"account_id": self.acc.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

        # other user can't list -> 404
        self.client.force_authenticate(user=self.other)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class TransactionsAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()
        self.u1 = self.User.objects.create_user(email="tx1@example.com", password="x")
        self.u2 = self.User.objects.create_user(email="tx2@example.com", password="x")
        self.a1 = Account.objects.create(user=self.u1, balance=Decimal("100.00"))
        self.a2 = Account.objects.create(user=self.u2, balance=Decimal("50.00"))
        self.a3 = Account.objects.create(user=self.u1, balance=Decimal("10.00"))

    def test_auth_required(self):
        url = reverse("transactions")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post(url, {}, format="json").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_transaction_success(self):
        self.client.force_authenticate(user=self.u1)
        url = reverse("transactions")
        payload = {
            "sender_account": str(self.a1.id),
            "receiver_account": str(self.a2.id),
            "amount": "40.00",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.a1.refresh_from_db(); self.a2.refresh_from_db()
        self.assertEqual(self.a1.balance, Decimal("60.00"))
        self.assertEqual(self.a2.balance, Decimal("90.00"))
        self.assertEqual(Decimal(str(res.data["sender_balance_after"])), Decimal("60.00"))
        self.assertEqual(Decimal(str(res.data["receiver_balance_after"])), Decimal("90.00"))

    def test_cannot_send_from_foreign_account(self):
        self.client.force_authenticate(user=self.u2)
        url = reverse("transactions")
        payload = {
            "sender_account": str(self.a1.id),  # owned by u1
            "receiver_account": str(self.a2.id),
            "amount": "10.00",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_send_to_same_account(self):
        self.client.force_authenticate(user=self.u1)
        url = reverse("transactions")
        payload = {
            "sender_account": str(self.a3.id),
            "receiver_account": str(self.a3.id),
            "amount": "1.00",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_only_user_related_transactions(self):
        # seed: one u1->u2 and one unrelated u2->u2 (different accounts)
        Transaction.objects.create(sender_account=self.a1, receiver_account=self.a2, amount=Decimal("5.00"))
        a4 = Account.objects.create(user=self.u2, balance=Decimal("30.00"))
        Transaction.objects.create(sender_account=self.a2, receiver_account=a4, amount=Decimal("5.00"))
        self.client.force_authenticate(user=self.u1)
        url = reverse("transactions")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Should include only the first transaction
        self.assertEqual(len(res.data), 1)
