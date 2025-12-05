"""
Serializers for API resources: users, accounts/cards, transfers, and bills.
Includes helper masking and per-request ownership scoping for safety.
"""

from decimal import Decimal

from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .convert_currency import eur_to_jod, jod_to_eur, jod_to_usd, usd_to_jod
from .models import Account, BillPayment, Biller, Card, Transaction, User


class UserCreateSerializer(BaseUserCreateSerializer):
    """Register a user with email/password/first_name."""

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ("email", "password", "first_name")


class UserSerializer(serializers.ModelSerializer):
    """Basic user info for embedding in other serializers."""

    class Meta:
        model = User
        fields = ("id", "first_name", "email", "is_staff", "is_superuser")


class CardSerializer(serializers.ModelSerializer):
    """
    Card read model that exposes only last4 and expiration.
    CVV and full card number are intentionally omitted.
    """

    last4 = serializers.SerializerMethodField()
    expiration_date = serializers.SerializerMethodField(
    )  # override for ISO date

    class Meta:
        model = Card
        fields = ["id", "card_type", "last4", "is_active", "expiration_date"]
        read_only_fields = ("is_active", )

    @extend_schema_field(serializers.CharField())
    def get_last4(self, obj) -> str:
        return obj.card_number[-4:]

    @extend_schema_field(serializers.DateField())
    def get_expiration_date(self, obj) -> str:
        value = obj.expiration_date
        if hasattr(value, "date"):
            value = value.date()
        return value.isoformat()


class AccountSerializer(serializers.ModelSerializer):
    """Account read model with masking, balance display, and limits."""

    mask = serializers.SerializerMethodField()
    maximum_withdrawal_amount = serializers.DecimalField(max_digits=12,
                                                         decimal_places=2,
                                                         read_only=True)
    card_count = serializers.SerializerMethodField()
    owner = UserSerializer(source="user", read_only=True)
    display_balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "account_number",
            "owner",
            "mask",
            "type",
            "currency",
            "balance",
            "display_balance",
            "is_active",
            "maximum_withdrawal_amount",
            "card_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "id",
            "account_number",
            "owner",
            "mask",
            "is_active",
            "maximum_withdrawal_amount",
            "card_count",
            "created_at",
            "updated_at",
        )

    @extend_schema_field(serializers.CharField())
    def get_mask(self, obj) -> str:
        n = len(obj.account_number)
        return f"{'*' * (n - 4)}{obj.account_number[-4:]}"

    @extend_schema_field(serializers.IntegerField())
    def get_card_count(self, obj) -> int:
        return obj.cards.count()

    class _BalanceDisplaySerializer(serializers.Serializer):
        currency = serializers.CharField()
        amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    @extend_schema_field(_BalanceDisplaySerializer)
    def get_display_balance(self, obj):
        """Show balance converted to the user's preferred currency (if different)."""
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated or not hasattr(
                user, "profile"):
            return {"currency": obj.currency, "amount": obj.balance}

        pref = user.profile.preferred_currency
        if pref == obj.currency:
            return {"currency": obj.currency, "amount": obj.balance}

        amount = obj.balance
        if obj.currency == "JOD" and pref == "USD":
            amount = jod_to_usd(obj.balance)
        elif obj.currency == "USD" and pref == "JOD":
            amount = usd_to_jod(obj.balance)
        elif obj.currency == "JOD" and pref == "EUR":
            amount = jod_to_eur(obj.balance)
        elif obj.currency == "EUR" and pref == "JOD":
            amount = eur_to_jod(obj.balance)

        return {"currency": pref, "amount": amount}


class TransactionSerializer(serializers.ModelSerializer):
    """Read-only representation of a transaction with account numbers."""

    sender_account_number = serializers.SerializerMethodField()
    receiver_account_number = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "sender_account_number",
            "receiver_account_number",
            "sender_balance_after",
            "receiver_balance_after",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_sender_account_number(self, obj) -> str:
        return obj.sender_account.account_number

    @extend_schema_field(serializers.CharField())
    def get_receiver_account_number(self, obj) -> str:
        return obj.receiver_account.account_number


class InternalTransferSerializer(serializers.Serializer):
    """
    Transfer between two accounts owned by the authenticated user.
    Sender/receiver querysets are restricted per-request for safety.
    """

    sender_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    receiver_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    amount = serializers.DecimalField(max_digits=12,
                                      decimal_places=2,
                                      min_value=Decimal("0.01"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        req = self.context.get("request")
        if req and req.user and req.user.is_authenticated:
            owned = Account.objects.filter(user=req.user, is_active=True)
            self.fields["sender_account"].queryset = owned
            self.fields["receiver_account"].queryset = owned

    def validate(self, attrs):
        if attrs["sender_account"].account_number == attrs[
                "receiver_account"].account_number:
            raise serializers.ValidationError(
                "Cannot transfer to the same account.")
        return attrs

    def create(self, validated):
        return Transaction.objects.create(
            sender_account=validated["sender_account"],
            receiver_account=validated["receiver_account"],
            amount=validated["amount"],
        )


class ExternalTransferSerializer(serializers.Serializer):
    """
    Transfer from one of the user's accounts to another user's account_number.
    Sender queryset is restricted per-request; receiver is looked up by number.
    """

    sender_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    receiver_account_number = serializers.CharField(max_length=12)
    amount = serializers.DecimalField(max_digits=12,
                                      decimal_places=2,
                                      min_value=Decimal("0.01"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        req = self.context.get("request")
        if req and req.user and req.user.is_authenticated:
            self.fields["sender_account"].queryset = Account.objects.filter(
                user=req.user, is_active=True)

    def validate(self, attrs):
        sender = attrs["sender_account"]
        try:
            receiver = Account.objects.get(
                account_number=attrs["receiver_account_number"],
                is_active=True)
        except Account.DoesNotExist:
            raise serializers.ValidationError(
                {"receiver_account_number": "Invalid destination."})

        if receiver.account_number == sender.account_number:
            raise serializers.ValidationError(
                "Cannot transfer to the same account.")

        attrs["receiver_account"] = receiver
        return attrs

    def create(self, validated):
        return Transaction.objects.create(
            sender_account=validated["sender_account"],
            receiver_account=validated["receiver_account"],
            amount=validated["amount"],
        )


class BillPaymentSerializer(serializers.ModelSerializer):
    """
    Create/list bill payments for the authenticated user.
    User is injected via HiddenField; account queryset is user-scoped.
    """

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())

    amount = serializers.DecimalField(max_digits=12,
                                      decimal_places=2,
                                      read_only=True)
    currency = serializers.CharField(read_only=True)

    class Meta:
        model = BillPayment
        fields = [
            "id",
            "user",
            "account",
            "biller",
            "reference_number",
            "amount",
            "currency",
            "status",
        ]
        read_only_fields = ("amount", "currency", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        req = self.context.get("request")
        if req and getattr(req.user, "is_authenticated", False):
            self.fields["account"].queryset = Account.objects.filter(
                user=req.user)
        else:
            self.fields["account"].queryset = Account.objects.none()

    def validate_account(self, account: Account):
        req = self.context.get("request")
        if req and getattr(req.user, "is_authenticated", False):
            if account.user_id != req.user.id:
                raise serializers.ValidationError(
                    "This account does not belong to you.")
        return account

    def validate(self, data):
        biller: Biller | None = data.get("biller")
        if biller and biller.fixed_amount <= 0:
            raise serializers.ValidationError(
                {"biller": "Biller has no payable fixed amount."})
        return data
