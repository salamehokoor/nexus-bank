from decimal import Decimal
from rest_framework import serializers
from .models import Account, Card, User, Transaction, BillPayment
from django.conf import settings
from .convert_currency import jod_to_usd, usd_to_jod, jod_to_eur, eur_to_jod
from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer


class UserCreateSerializer(BaseUserCreateSerializer):

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ("email", "password", "first_name")


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = ("id", 'first_name', 'email', 'is_staff', 'is_superuser')


class CardSerializer(serializers.ModelSerializer):
    last4 = serializers.SerializerMethodField()
    expiration_date = serializers.SerializerMethodField()  # <- override

    class Meta:
        model = Card
        fields = ["id", "card_type", "last4", "is_active", "expiration_date"]

    def get_last4(self, obj):
        return obj.card_number[-4:]

    def get_expiration_date(self, obj):
        value = obj.expiration_date
        # if it's datetime, convert to date; then ISO string
        if hasattr(value, "date"):
            value = value.date()
        return value.isoformat()

    read_only_fields = ("is_active")


class AccountSerializer(serializers.ModelSerializer):
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
            "currency",  # new field
            "balance",
            "display_balance",  # new field
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

    def get_mask(self, obj):
        n = len(obj.account_number)
        return f"{'*' * (n - 4)}{obj.account_number[-4:]}"

    def get_card_count(self, obj):
        return obj.cards.count()

    def get_display_balance(self, obj):
        """Show balance converted to the user's preferred currency (if different)."""
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated or not hasattr(
                user, "profile"):
            # no preference → show native account currency
            return {"currency": obj.currency, "amount": obj.balance}

        pref = user.profile.preferred_currency
        # If same currency → show as-is
        if pref == obj.currency:
            return {"currency": obj.currency, "amount": obj.balance}

        # Use conversion helpers from
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


# ---------- read shape (reuse for responses) ----------
class TransactionSerializer(serializers.ModelSerializer):
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

    def get_sender_account_number(self, obj):
        return obj.sender_account.account_number

    def get_receiver_account_number(self, obj):
        return obj.receiver_account.account_number


# ---------- INTERNAL: same-user -> same-user ----------
class InternalTransferSerializer(serializers.Serializer):
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


# ---------- EXTERNAL: my account -> other user's specific account ----------
class ExternalTransferSerializer(serializers.Serializer):
    # I select which of *my* accounts to send from (limit to my accounts)
    sender_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    # I specify the recipient by their public account_number (don’t expose their IDs)
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
        req = self.context["request"]
        sender = attrs["sender_account"]
        # Look up recipient by account_number; keep generic error to avoid enumeration
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
        # allow sending to self? if you want to forbid self-user here:
        # if receiver.user_id == req.user.id:
        #     raise serializers.ValidationError("Use internal transfer for your own accounts.")

        attrs["receiver_account"] = receiver
        return attrs

    def create(self, validated):
        return Transaction.objects.create(
            sender_account=validated["sender_account"],
            receiver_account=validated["receiver_account"],
            amount=validated["amount"],
        )


class BillPaymentSerializer(serializers.ModelSerializer):
    biller_name = serializers.ReadOnlyField(source="biller.name")

    class Meta:
        model = BillPayment
        fields = [
            "id", "biller", "biller_name", "account", "reference_number",
            "amount", "currency", "status", "created_at"
        ]
        read_only_fields = ["amount", "currency", "status", "created_at"]

    def validate_account(self, value):
        user = self.context["request"].user
        if value.user != user:
            raise serializers.ValidationError(
                "You can only use your own accounts for bill payments.")
        return value

    def create(self, validated_data):
        payment = BillPayment.objects.create(**validated_data)
        payment.pay()
        return payment
