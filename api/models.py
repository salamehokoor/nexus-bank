from django.db import models, transaction
from .managers import UserManager
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.db.models import Q
import uuid  # <-- ADDED for Card Manager
from datetime import datetime  # <-- ADDED for Card Manager


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

    # --- FIX: Added 'groups' to prevent clash ---
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="api_user_groups",
    )

    def __str__(self):
        return self.email


class UserProfile(BaseModel):
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name='profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class UserAddress(BaseModel):
    user = models.ForeignKey(User,
                             on_delete=models.CASCADE,
                             related_name='addresses')
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.street}, {self.city}"


class AccountManager(models.Manager):

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

    objects = AccountManager()  # Use the default manager

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


# --- NEW CARD MODEL AND MANAGER ---


class CardManager(models.Manager):

    def create_card(self, account, card_type):
        """
        Generates a new card for a given account.
        """
        # Generate a 16-digit card number
        # Using first 16 chars of a UUID is a simple, non-sequential way
        card_number = str(uuid.uuid4().int)[:16]

        # Generate a 3-digit CVV
        cvv = str(uuid.uuid4().int)[:3]

        # Set expiration date 5 years from now
        today = datetime.now()
        expiration_date = today.replace(year=today.year + 5)

        card = self.model(account=account,
                          card_type=card_type,
                          card_number=card_number,
                          cvv=cvv,
                          expiration_date=expiration_date)
        card.save()
        return card


class Card(BaseModel):
    """
    Represents a physical or virtual card linked to an account.
    """

    class CardType(models.TextChoices):
        DEBIT = 'DEBIT', 'Debit Card'
        CREDIT = 'CREDIT', 'Credit Card'

    # This links the card to *one* account
    account = models.ForeignKey(Account,
                                on_delete=models.CASCADE,
                                related_name='cards')

    card_type = models.CharField(max_length=10,
                                 choices=CardType.choices,
                                 default=CardType.DEBIT)
    card_number = models.CharField(max_length=16, unique=True, editable=False)
    cvv = models.CharField(max_length=3, editable=False)
    expiration_date = models.DateField(editable=False)
    is_active = models.BooleanField(default=True)

    objects = CardManager()

    def __str__(self):
        # Shows the last 4 digits, e.g., "DEBIT (**** 1234)"
        return f"{self.get_card_type_display()} (**** {self.card_number[-4:]})"


# --- TRANSACTION MODEL AND MANAGER ---


# This creates a "Manager", a helper class for your model.
class TransactionManager(models.Manager):

    # This is the main function we will call to make a transfer.
    # It takes the sender's account object, the receiver's account number,
    # and the amount.
    def create_transaction(self,
                           sender_account,
                           receiver_account_number,
                           amount,
                           receiver_ifsc=None):

        # --- CHECK 1: Do you have enough money? ---
        # If the sender's balance is less than the amount, stop right here.
        if sender_account.balance < amount:
            raise ValueError("Insufficient funds.")

        # --- TRY BLOCK: Try to run all the code inside. ---
        # If any part fails, the "except" blocks at the end will run.
        try:
            # --- THE MOST IMPORTANT LINE! ---
            # This tells the database: "Treat everything inside this block
            # as ONE SINGLE operation. If ANY part fails, undo EVERYTHING."
            # This is the "all-or-nothing" rule. It prevents money from
            # being lost if the server crashes.
            with transaction.atomic():

                # --- STEP 1: Find the receiver's account ---
                # Search the Account table for an account with this number.
                receiver_account = Account.objects.get(
                    account_number=receiver_account_number)

                # --- STEP 2: Debit the sender ---
                # Subtract the amount from the sender's balance
                sender_account.balance -= amount
                # Save this change to the database
                sender_account.save()

                # --- STEP 3: Credit the receiver ---
                # Add the amount to the receiver's balance
                receiver_account.balance += amount
                # Save this change to the database
                receiver_account.save()

                # --- STEP 4: Create the "Receipt" ---
                # 'self.model' is a shortcut for the Transaction model.
                # We are creating a new Transaction object to keep
                # a record of what just happened.
                tx = self.model(
                    sender_account=sender_account,
                    receiver_account=receiver_account,
                    amount=amount,
                    # We save the *new* balances for the bank statement
                    sender_balance_after=sender_account.balance,
                    receiver_balance_after=receiver_account.balance)
                # Save the new "receipt" to the database
                tx.save()

                # Return the new "receipt" object
                return tx

        # --- ERROR HANDLING 1 ---
        # If Account.objects.get(...) failed, this code runs.
        except Account.DoesNotExist:
            raise ValueError("Receiver account not found in this bank.")

        # --- ERROR HANDLING 2 ---
        # If *any other* error happens (like a database crash),
        # transaction.atomic() will undo everything, and this code will run.
        except Exception as e:
            raise ValueError(f"Transaction failed: {e}")


# This is the actual database model (the "table")
class Transaction(BaseModel):

    # A link to the sender's account. If the account is deleted,
    # all its transactions are also deleted (on_delete=models.CASCADE).
    sender_account = models.ForeignKey(Account,
                                       related_name='sent_transactions',
                                       on_delete=models.CASCADE)

    # A link to the receiver's account.
    receiver_account = models.ForeignKey(Account,
                                         related_name='received_transactions',
                                         on_delete=models.CASCADE)

    # How much money was sent.
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # A snapshot of the sender's balance *after* the transfer
    sender_balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    # A snapshot of the receiver's balance *after* the transfer
    receiver_balance_after = models.DecimalField(max_digits=12,
                                                 decimal_places=2)

    # --- This is the "magic link" ---
    # This line tells the Transaction model:
    # "Instead of the default manager, use the TransactionManager as your
    # 'objects' manager."
    # This is what lets us call `Transaction.objects.create_transaction(...)`
    objects = TransactionManager()

    # This just makes sure when you look at a list of transactions,
    # the newest ones are at the top.
    class Meta:
        ordering = ['-created_at']

    # This defines how the object is printed (e.g., in the admin panel)
    def __str__(self):
        return f"{self.amount} from {self.sender_account} to {self.receiver_account}"
