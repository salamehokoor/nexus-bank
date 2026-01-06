"""
Core banking models: users, accounts/cards, transactions, bill payments, and OTP verification.
Implements balance updates atomically and handles basic FX conversions.
"""

import random
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models, transaction
from django.db.models import Q, F
from django.utils import timezone

from .convert_currency import jod_to_usd, usd_to_jod, jod_to_eur, eur_to_jod, usd_to_eur, eur_to_usd


def generate_cvv():
    """Generate a short random CVV placeholder (3 digits)."""
    return str(uuid.uuid4().int)[:3]


def generate_account_number_default():
    """Generate a 12-digit account number string."""
    return str(uuid.uuid4().int)[:12]


def default_expiration_date():
    """Five-year expiry from now without freezing defaults in migrations."""
    now = timezone.now()
    return now.date().replace(year=now.year + 5)


class BaseModel(models.Model):
    """Shared timestamp fields for auditable models."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------- Manager ----------
class UserManager(BaseUserManager):
    """Custom manager that uses email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


# ---------- User ----------
class User(AbstractUser):
    """Email-based user with `username` removed."""
    username = None
    email = models.EmailField(unique=True)
    is_online = models.BooleanField(default=False)
    country = models.CharField(max_length=100, blank=True, default="")
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


# ---------- Profile ----------
class UserProfile(BaseModel):
    """Basic profile data for a user."""
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name='profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# ---------- Address ----------
class UserAddress(BaseModel):
    """Physical address linked to a user."""
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='addresses')
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.street}, {self.city}"


class Account(BaseModel):
    """
    Customer bank account with currency support and per-type limits.
    Uses a 12-digit generated account_number as primary identifier.
    """

    class AccountTypes(models.TextChoices):
        SAVINGS = 'Savings', 'Savings Account'
        SALARY = 'Salary', 'Salary Account'
        BASIC = 'Basic', 'Basic Account'
        USD = 'USD', 'USD Account'
        EUR = 'EUR', 'EUR Account'

    CURRENCY_CHOICES = [
        ('JOD', 'JOD'),
        ('USD', 'USD'),
        ('EUR', 'EUR'),
    ]

    @staticmethod
    def generate_account_number():
        # Backward-compat for historical migrations; uses module helper.
        return generate_account_number_default()

    account_number = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        default=generate_account_number_default,
        primary_key=True,
    )

    type = models.CharField(
        max_length=10,
        choices=AccountTypes.choices,
        default=AccountTypes.BASIC,
    )

    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='accounts')
    balance = models.DecimalField(max_digits=12,
                                  decimal_places=2,
                                  default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)

    currency = models.CharField(max_length=3,
                                choices=CURRENCY_CHOICES,
                                default='JOD')

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(balance__gte=0),
                                   name='account_balance_nonnegative'),
        ]

    LIMITS = {
        AccountTypes.SAVINGS: Decimal('10000.00'),
        AccountTypes.SALARY: Decimal('10000.00'),
        AccountTypes.BASIC: Decimal('10000.00'),
        AccountTypes.USD: Decimal('10000.00'),
        AccountTypes.EUR: Decimal('10000.00'),
    }

    @property
    def maximum_withdrawal_amount(self) -> Decimal:
        return self.LIMITS[self.type]

    def __str__(self):
        return f"{self.account_number}"


class Card(BaseModel):
    """
    Represents a physical or virtual card linked to an account.
    Automatically generates a 16-digit number, CVV, and expiration date.
    """

    class CardType(models.TextChoices):
        DEBIT = 'DEBIT', 'Debit Card'
        CREDIT = 'CREDIT', 'Credit Card'

    def generate_card_number():
        return str(uuid.uuid4().int)[:16]

    # This links the card to *one* account
    account = models.ForeignKey(Account,
                                on_delete=models.CASCADE,
                                related_name='cards')

    card_type = models.CharField(max_length=10,
                                 choices=CardType.choices,
                                 default=CardType.DEBIT)
    card_number = models.CharField(
        max_length=16,
        unique=True,
        editable=False,
        default=generate_card_number,
    )

    cvv = models.CharField(max_length=3, editable=False, default=generate_cvv)

    expiration_date = models.DateField(editable=False,
                                       default=default_expiration_date)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.card_number}"


class Transaction(BaseModel):
    """
    Represents a transfer between two accounts with balance snapshots.
    Balance updates and FX conversions are executed atomically.
    """
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REVERSED = "REVERSED", "Reversed"
        PENDING_OTP = "PENDING_OTP", "Pending OTP"

    sender_account = models.ForeignKey(Account,
                                       related_name='sent_transactions',
                                       on_delete=models.CASCADE)

    receiver_account = models.ForeignKey(Account,
                                         related_name='received_transactions',
                                         on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    fee_amount = models.DecimalField(max_digits=12,
                                     decimal_places=2,
                                     default=Decimal('0.00'))

    status = models.CharField(max_length=16,
                              choices=Status.choices,
                              default=Status.SUCCESS)

    idempotency_key = models.CharField(max_length=64,
                                       blank=True,
                                       null=True,
                                       unique=True)

    sender_balance_after = models.DecimalField(max_digits=12,
                                               decimal_places=2,
                                               editable=False,
                                               null=True)

    receiver_balance_after = models.DecimalField(max_digits=12,
                                                 decimal_places=2,
                                                 editable=False,
                                                 null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(check=Q(amount__gt=0),
                                   name='positive_transaction_amount')
        ]

    def execute_transaction(self):
        """
        Executes the balance movement atomically.
        Should only be called when status is confirmed as SUCCESS.
        """
        with transaction.atomic():
            # Reload to lock
            sa = Account.objects.select_for_update().get(pk=self.sender_account_id)
            ra = Account.objects.select_for_update().get(pk=self.receiver_account_id)

            if sa.pk == ra.pk:
                raise ValueError("Cannot transfer to the same account.")
            if self.amount <= 0:
                raise ValueError("Amount must be positive.")

            fee_amount = self.fee_amount or Decimal("0.00")
            total_debit = (self.amount + fee_amount)

            if sa.balance < total_debit:
                raise ValueError("Insufficient funds.")

            # --- Handle currency conversion ---
            credited = self.amount
            if sa.currency != ra.currency:
                pair = (sa.currency, ra.currency)
                if pair == ('JOD', 'USD'):
                    credited = jod_to_usd(self.amount)
                elif pair == ('USD', 'JOD'):
                    credited = usd_to_jod(self.amount)
                elif pair == ('JOD', 'EUR'):
                    credited = jod_to_eur(self.amount)
                elif pair == ('EUR', 'JOD'):
                    credited = eur_to_jod(self.amount)
                elif pair == ('USD', 'EUR'):
                    credited = usd_to_eur(self.amount)
                elif pair == ('EUR', 'USD'):
                    credited = eur_to_usd(self.amount)
                else:
                    raise ValueError(f"Unsupported currency pair: {pair}")

            # --- Update balances atomically ---
            Account.objects.filter(pk=sa.pk).update(balance=F("balance") - total_debit)
            Account.objects.filter(pk=ra.pk).update(balance=F("balance") + credited)

            # --- Refresh updated balances ---
            sa.refresh_from_db(fields=["balance"])
            ra.refresh_from_db(fields=["balance"])

            self.sender_balance_after = sa.balance
            self.receiver_balance_after = ra.balance
            
            # Save the transaction record with updated balances
            # Use super().save to avoid infinite recursion if we called self.save()
            super().save(update_fields=['sender_balance_after', 'receiver_balance_after', 'status'])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # If we are creating a new transaction and it IS SUCCESS, execute immediately.
        # If it is PENDING_OTP, just save the record without moving money.
        if is_new:
            if self.status == self.Status.SUCCESS:
                # We save first to get an ID (sometimes advantageous), but here
                # execute_transaction expects to find the accounts.
                # Actually execute_transaction updates THIS instance's balance fields.
                # Let's save first partially to ensure we have an ID if needed, 
                # but standard practice: do the logic, then save.
                
                # However, our execute_transaction calls select_for_update on accounts,
                # then updates accounts, then updates self.
                # We can call it here.
                if self.sender_balance_after is None:
                    self.sender_balance_after = Decimal("0.00")
                if self.receiver_balance_after is None:
                    self.receiver_balance_after = Decimal("0.00")
                
                # We must save once to exist? Not strictly necessary for the logic but safer.
                super().save(*args, **kwargs)
                self.execute_transaction()
                return

        # Fallback for non-SUCCESS or existing updates
        if self.sender_balance_after is None:
             self.sender_balance_after = Decimal("0.00")
        if self.receiver_balance_after is None:
             self.receiver_balance_after = Decimal("0.00")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.amount} from {self.sender_account} to {self.receiver_account}"


class Biller(models.Model):
    """Entity that collects fixed-amount bill payments into a system account."""
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50,
                                choices=[('Electricity', 'Electricity'),
                                         ('Water', 'Water'),
                                         ('Internet', 'Internet'),
                                         ('Telecom', 'Telecom'),
                                         ('Other', 'Other')])
    description = models.TextField(blank=True, null=True)
    fixed_amount = models.DecimalField(max_digits=12,
                                       decimal_places=2,
                                       default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    # money for this biller is collected into this account
    system_account = models.OneToOneField(Account,
                                          on_delete=models.CASCADE,
                                          related_name='biller_system_account',
                                          null=True,
                                          blank=True)

    def __str__(self):
        return self.name


class BillPayment(models.Model):
    """
    Represents a single bill payment against a biller.
    Amount and currency are enforced from the biller/account on creation.
    """
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name="bill_payments")
    account = models.ForeignKey(Account,
                                on_delete=models.CASCADE,
                                related_name="bill_payments")
    biller = models.ForeignKey(Biller,
                               on_delete=models.CASCADE,
                               related_name="payments")
    reference_number = models.CharField(max_length=30, unique=True)
    amount = models.DecimalField(max_digits=12,
                                 decimal_places=2)  # auto-set from biller
    currency = models.CharField(max_length=3,
                                choices=[('JOD', 'JOD'), ('USD', 'USD'),
                                         ('EUR', 'EUR')])
    status = models.CharField(max_length=20,
                              choices=[('PENDING', 'Pending'),
                                       ('PAID', 'Paid'), ('FAILED', 'Failed')],
                              default='PENDING')
    idempotency_key = models.CharField(max_length=64,
                                       blank=True,
                                       null=True,
                                       unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # on create, enforce fixed amount and account currency
        if not self.pk:
            self.amount = self.biller.fixed_amount
            self.currency = self.account.currency
        super().save(*args, **kwargs)

    def pay(self):
        """Debit user's account and credit biller.system_account (with FX)."""
        if not self.biller.system_account:
            raise ValueError(f"{self.biller.name} has no system account.")
        sender = self.account
        receiver = self.biller.system_account

        with transaction.atomic():  # commit/rollback as one unit
            tx = Transaction.objects.create(
                sender_account=sender,
                receiver_account=receiver,
                amount=self.amount,
                fee_amount=Decimal("0.00"),
                status=Transaction.Status.SUCCESS,
            )
            self.status = 'PAID'
            super().save(update_fields=['status'])
            return tx


class Notification(BaseModel):
    """
    Stores notification history for users.
    Notifications are created by signals and can be retrieved via REST API.
    """

    class NotificationType(models.TextChoices):
        TRANSACTION = "TRANSACTION", "Transaction"
        SECURITY = "SECURITY", "Security"
        ADMIN_ALERT = "ADMIN_ALERT", "Admin Alert"
        BILL_PAYMENT = "BILL_PAYMENT", "Bill Payment"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.TRANSACTION,
    )
    is_read = models.BooleanField(default=False)

    # Optional: link to related transaction for context
    related_transaction = models.ForeignKey(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.message[:50]}"


class OTPVerification(models.Model):
    """
    One-Time Password verification for Login-2FA only.
    For high-value transfers, use TransferOTP model.
    """

    class Purpose(models.TextChoices):
        LOGIN = "LOGIN", "Login Verification"
        # Transaction purpose moved to TransferOTP, kept for legacy/login compat
        TRANSACTION = "TRANSACTION", "Transaction Authorization"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otp_codes",
    )
    code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "-created_at"]),
            models.Index(fields=["code", "is_verified"]),
        ]

    def __str__(self):
        return f"OTP {self.code} for {self.user.email} ({self.purpose})"

    @classmethod
    def generate(cls, user, purpose: str, validity_minutes: int = 5):
        # ... logic mainly for Login ...
        # Invalidate existing unused codes for this user/purpose
        cls.objects.filter(
            user=user,
            purpose=purpose,
            is_verified=False,
        ).update(is_verified=True)  # Mark as verified to prevent reuse

        code = "".join([str(random.randint(0, 9)) for _ in range(6)])
        
        otp = cls.objects.create(
            user=user,
            code=code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=validity_minutes),
        )
        return otp
    
    @classmethod
    def verify_code(cls, user, code: str, purpose: str) -> bool:
        try:
            otp = cls.objects.get(
                user=user,
                code=code,
                purpose=purpose,
                is_verified=False,
            )
            # Basic validation
            if timezone.now() < otp.expires_at:
                otp.is_verified = True
                otp.save(update_fields=["is_verified"])
                return True
            return False
        except cls.DoesNotExist:
            return False


import hashlib
import secrets

class TransferOTP(models.Model):
    """
    Dedicated OTP for authorized transfer confirmation.
    Stores hashed OTP for security.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transfer_otps")
    transfer = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="otp_request")
    
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    MAX_ATTEMPTS = 3
    VALIDITY_MINUTES = 5

    def __str__(self):
        return f"TransferOTP for {self.transfer.id}"

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @classmethod
    def generate(cls, user, transfer):
        # Generate 6 digit crypto-safe string
        code = "".join([str(secrets.randbelow(10)) for _ in range(6)])
        code_hash = cls.hash_code(code)
        
        expires = timezone.now() + timedelta(minutes=cls.VALIDITY_MINUTES)
        
        instance = cls.objects.create(
            user=user,
            transfer=transfer,
            code_hash=code_hash,
            expires_at=expires,
        )
        return instance, code

    def verify(self, raw_code: str) -> bool:
        if self.is_used:
            return False
        if timezone.now() > self.expires_at:
            return False
        if self.attempts >= self.MAX_ATTEMPTS:
            return False
            
        hashed = self.hash_code(raw_code)
        if hashed == self.code_hash:
            return True
        else:
            self.attempts += 1
            self.save(update_fields=['attempts'])
            return False


