from django.db import models, transaction
from django.contrib.auth.models import AbstractUser, Permission, BaseUserManager
from decimal import Decimal
from django.db.models import Q, F
import uuid
from datetime import datetime


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------- Manager ----------
class UserManager(BaseUserManager):

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
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


# ---------- Profile ----------
class UserProfile(BaseModel):
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
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='addresses')
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.street}, {self.city}"


class Account(BaseModel):

    class AccountTypes(models.TextChoices):
        SAVINGS = 'Savings', 'Savings Account'
        SALARY = 'Salary', 'Salary Account'
        BASIC = 'Basic', 'Basic Account'

    def generate_account_number():
        # ensures 12-digit string
        return str(uuid.uuid4().int)[:12]

    account_number = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        default=generate_account_number,
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

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(balance__gte=0),
                                   name='account_balance_nonnegative'),
        ]

    LIMITS = {
        AccountTypes.SAVINGS: Decimal('10000.00'),
        AccountTypes.SALARY: Decimal('10000.00'),
        AccountTypes.BASIC: Decimal('10000.00'),
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

    cvv = models.CharField(max_length=3,
                           editable=False,
                           default=str(uuid.uuid4().int)[:3])

    expiration_date = models.DateField(
        editable=False,
        default=datetime.now().replace(year=datetime.now().year + 5))
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.card_number}"


class Transaction(BaseModel):

    sender_account = models.ForeignKey(Account,
                                       related_name='sent_transactions',
                                       on_delete=models.CASCADE)

    receiver_account = models.ForeignKey(Account,
                                         related_name='received_transactions',
                                         on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    sender_balance_after = models.DecimalField(max_digits=12,
                                               decimal_places=2,
                                               editable=False)

    receiver_balance_after = models.DecimalField(max_digits=12,
                                                 decimal_places=2,
                                                 editable=False)

    # This just makes sure when you look at a list of transactions,
    # the newest ones are at the top.
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(check=Q(amount__gt=0),
                                   name='positive_transaction_amount')
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            return super().save(*args, **kwargs)

        with transaction.atomic():
            # These hold the PK ('account_number') because Account.account_number is primary_key=True
            sa = Account.objects.select_for_update().get(
                pk=self.sender_account_id)
            ra = Account.objects.select_for_update().get(
                pk=self.receiver_account_id)

            if sa.pk == ra.pk:
                raise ValueError("Cannot transfer to the same account.")
            if self.amount <= 0:
                raise ValueError("Amount must be positive.")
            if sa.balance < self.amount:
                raise ValueError("Insufficient funds.")

            Account.objects.filter(pk=sa.pk).update(balance=F("balance") -
                                                    self.amount)
            Account.objects.filter(pk=ra.pk).update(balance=F("balance") +
                                                    self.amount)

            sa.refresh_from_db(fields=["balance"])
            ra.refresh_from_db(fields=["balance"])

            self.sender_balance_after = sa.balance
            self.receiver_balance_after = ra.balance

            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.amount} from {self.sender_account} to {self.receiver_account}"
