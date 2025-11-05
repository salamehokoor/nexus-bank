# api/models.py

from django.db import models
from django.db import transaction  # For safe, atomic transactions
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


# --- Base Model (From File 2) ---
# This is a template to add tracking fields to all other models.
# It's the most "DRY" (Don't Repeat Yourself) and efficient pattern.
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # This tells Django it's not a real table.


# --- User & Profile Models (Best of File 1, 2, & 3) ---


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # --- ADD THESE TWO FIELDS TO FIX THE ERROR ---
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        # This new related_name fixes the clash
        related_name="api_user_groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        # This new related_name fixes the clash
        related_name="api_user_permissions",
    )

    # --- END OF FIX ---

    def __str__(self):
        return self.email


class UserProfile(BaseModel):
    """
    (From File 2)
    This holds all personal data related to a user.
    It links one-to-one with the User.
    """
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name='profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()

    # This is a good place for 'fathername', 'mothername' if you need them.
    # This is also where you'd put 'cpf', 'rg' from File 2's NaturalPerson.

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class UserAddress(BaseModel):
    """
    (From File 1 & 2)
    A separate model for addresses. Using a ForeignKey means
    a user can have multiple addresses (e.g., mailing, billing).
    """
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='addresses')
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.street}, {self.city}"


# --- Bank Structure Models (Best of File 1 & 3) ---


class BankAccountType(BaseModel):
    """
    (From File 1)
    This brilliant model defines the *rules* for an account,
    like interest rates and withdrawal limits.
    """
    name = models.CharField(max_length=100,
                            unique=True)  # e.g., "Checking", "Savings"
    maximum_withdrawal_amount = models.DecimalField(max_digits=12,
                                                    decimal_places=2)
    annual_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0),
                    MaxValueValidator(100)])

    def __str__(self):
        return self.name


class Branch(BaseModel):
    """
    (From File 3)
    Stores information about a specific bank branch.
    """
    name = models.CharField(max_length=100)
    ifsc_code = models.CharField(max_length=11, unique=True)
    address = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# --- Account & Transaction Models (Most Efficient Design) ---


class AccountManager(models.Manager):
    """
    A custom manager to safely handle account number generation.
    This logic should NOT be in the models.save() method.
    """

    def create_account(self,
                       user,
                       account_type,
                       branch,
                       initial_balance=Decimal('0.00')):
        # This is just an example. In production, you would use a more robust
        # service to guarantee a unique, non-guessable account number.
        # But even this is safer than File 3's .save() logic.
        last_account = self.model.objects.order_by('-id').first()
        new_account_number = str((last_account.id if last_account else 0) +
                                 1).zfill(12)

        account = self.model(account_number=new_account_number,
                             account_type=account_type,
                             branch=branch,
                             balance=initial_balance)
        account.save()
        account.users.add(user)  # Add the user to the ManyToManyField
        return account


class Account(BaseModel):
    """
    (Best of all 3 files)
    This is the central model.
    """
    # (From File 2) Using ManyToManyField allows for joint accounts.
    users = models.ManyToManyField(User, related_name='accounts')

    # (From File 1) Links to the rules for this account.
    account_type = models.ForeignKey(BankAccountType, on_delete=models.PROTECT)

    # (From File 3) Links to the branch that holds the account.
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)

    account_number = models.CharField(max_length=12,
                                      unique=True,
                                      editable=False)

    # (From File 1) Using max_digits=12 is safer.
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    objects = AccountManager()  # Use the custom manager

    def __str__(self):
        return self.account_number


class TransactionManager(models.Manager):

    def create_transaction(self,
                           sender_account,
                           receiver_account_number,
                           amount,
                           receiver_ifsc=None):
        """
        This is the correct, SAFE way to handle a transaction.
        We wrap the entire operation in `transaction.atomic()`.
        This means if *any* part fails, the *entire* thing is rolled back.
        No money can ever be "lost".
        """
        if sender_account.balance < amount:
            raise ValueError("Insufficient funds.")

        # Default to this bank's IFSC if none is provided
        if receiver_ifsc is None:
            receiver_ifsc = sender_account.branch.ifsc_code

        try:
            # We wrap this in a single atomic block
            with transaction.atomic():
                # 1. Find the receiver account
                receiver_account = Account.objects.get(
                    account_number=receiver_account_number,
                    branch__ifsc_code=receiver_ifsc)

                # 2. Debit the sender
                sender_account.balance -= amount
                sender_account.save()

                # 3. Credit the receiver
                receiver_account.balance += amount
                receiver_account.save()

                # 4. Create the transaction *record* (the ledger)
                # Note: We are just *creating a record* of what happened.
                # The logic is not in the model's .save() method.
                tx = self.model(
                    sender_account=sender_account,
                    receiver_account=receiver_account,
                    amount=amount,
                    sender_balance_after=sender_account.balance,
                    receiver_balance_after=receiver_account.balance)
                tx.save()
                return tx

        except Account.DoesNotExist:
            # This is where you would handle an external transfer
            # For now, we'll just raise an error
            raise ValueError("Receiver account not found in this bank.")
        except Exception as e:
            # Any other error (e.g., database connection)
            raise ValueError(f"Transaction failed: {e}")


class Transaction(BaseModel):
    """
    (Best of File 2 & 3)
    This model is a *record* or *ledger*. It does NOT contain
    the logic for the transfer. The logic is in the Manager.
    """
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

    objects = TransactionManager()  # Use the custom manager

    class Meta:
        ordering = ['-created_at']  # Show newest transactions first

    def __str__(self):
        return f"{self.amount} from {self.sender_account} to {self.receiver_account}"
