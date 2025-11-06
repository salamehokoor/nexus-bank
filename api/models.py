from django.db import models, transaction
from .managers import UserManager
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.db.models import Q


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()

    # Avoid reverse name clashes on permissions
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="api_user_permissions",
    )

    def __str__(self):
        return self.email


class UserProfile(BaseModel):
    """
    This holds all personal data related to a user.
    It links one-to-one with the User.
    """
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name='profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class UserAddress(BaseModel):
    """
    A separate model for addresses. Using a ForeignKey means
    a user can have multiple addresses (e.g., mailing, billing).
    """
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='addresses')
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.street}, {self.city}"


class AccountManager(models.Manager):
    """
    A custom manager to safely handle account number generation.
    This logic should NOT be in the models.save() method.
    """

    def create_account(self,
                       user,
                       account_type,
                       initial_balance=Decimal('0.00')):
        last_account = self.model.objects.order_by('-id').first()
        new_account_number = str((last_account.id if last_account else 0) +
                                 1).zfill(12)

        account = self.model(
            user=user,  # FK (one user -> many accounts)
            account_number=new_account_number,
            account_type=account_type,
            balance=initial_balance)
        account.save()
        return account


class Account(BaseModel):

    class AccountTypes(models.TextChoices):
        SAVINGS = 'Savings', 'Savings Account'
        SALARY = 'Salary', 'Salary Account'
        BASIC = 'Basic', 'Basic Account'

    # Account type as string (not integer)
    type = models.CharField(
        max_length=10,
        choices=AccountTypes.choices,
        default=AccountTypes.BASIC,
    )

    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='accounts')
    account_number = models.CharField(max_length=12,
                                      unique=True,
                                      editable=False)
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
        return f"{self.user.email} - {self.account_number} ({self.get_type_display()})"


class TransactionManager(models.Manager):

    def create_transaction(self,
                           sender_account,
                           receiver_account_number,
                           amount,
                           receiver_ifsc=None):
        """
        Minimal-change version of a safe transaction:
        wrapped in transaction.atomic(). For production, consider
        select_for_update() + F() expressions for concurrency.
        """
        if sender_account.balance < amount:
            raise ValueError("Insufficient funds.")

        try:
            with transaction.atomic():
                # 1. Find the receiver account
                receiver_account = Account.objects.get(
                    account_number=receiver_account_number)

                # 2. Debit the sender
                sender_account.balance -= amount
                sender_account.save()

                # 3. Credit the receiver
                receiver_account.balance += amount
                receiver_account.save()

                # 4. Create the transaction record (ledger)
                tx = self.model(
                    sender_account=sender_account,
                    receiver_account=receiver_account,
                    amount=amount,
                    sender_balance_after=sender_account.balance,
                    receiver_balance_after=receiver_account.balance)
                tx.save()
                return tx

        except Account.DoesNotExist:
            raise ValueError("Receiver account not found in this bank.")
        except Exception as e:
            raise ValueError(f"Transaction failed: {e}")


class Transaction(BaseModel):
    sender_account = models.ForeignKey(Account,
                                       related_name='sent_transactions',
                                       on_delete=models.CASCADE)
    receiver_account = models.ForeignKey(Account,
                                         related_name='received_transactions',
                                         on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Store the balance *after* the transaction for easy bank statements
    sender_balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    receiver_balance_after = models.DecimalField(max_digits=12,
                                                 decimal_places=2)

    objects = TransactionManager()

    class Meta:
        ordering = ['-created_at']  # Show newest transactions first

    def __str__(self):
        return f"{self.amount} from {self.sender_account} to {self.receiver_account}"
