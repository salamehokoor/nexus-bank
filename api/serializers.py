"""
Serializers for API resources: users, accounts/cards, transfers, bills, and notifications.
Includes helper masking, per-request ownership scoping, and OTP validation for high-value transfers.
"""

from decimal import Decimal

from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .convert_currency import eur_to_jod, jod_to_eur, jod_to_usd, usd_to_jod
from .models import Account, BillPayment, Biller, Card, Notification, OTPVerification, Transaction, User

# Threshold for requiring OTP on transfers
HIGH_VALUE_TRANSFER_THRESHOLD = Decimal("500.00")
EXTERNAL_TRANSFER_FEE_PERCENTAGE = Decimal("0.01")  # 1% fee


class UserCreateSerializer(BaseUserCreateSerializer):
    """Register a user with email/password/first_name."""

    class Meta(BaseUserCreateSerializer.Meta):
        model = User
        fields = ("email", "password", "first_name", "country")


class UserSerializer(serializers.ModelSerializer):
    """Basic user info for embedding in other serializers."""

    class Meta:
        model = User
        fields = ("id", "first_name", "email", "country", "is_staff",
                  "is_superuser")


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


class CardUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating card status (Freezing/Unfreezing).
    """
    class Meta:
        model = Card
        fields = ["is_active"]


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

        # Handle missing user, unauthenticated, or missing profile gracefully
        if not user or not user.is_authenticated:
            return {"currency": obj.currency, "amount": obj.balance}

        profile = getattr(user, "profile", None)
        if not profile:
            return {"currency": obj.currency, "amount": obj.balance}

        pref = getattr(profile, "preferred_currency", None)
        if not pref or pref == obj.currency:
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
            "fee_amount",
            "status",
            "idempotency_key",
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
    OTP required for amounts > 500.
    """

    sender_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    receiver_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    amount = serializers.DecimalField(max_digits=12,
                                      decimal_places=2,
                                      min_value=Decimal("0.01"))
    idempotency_key = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True)
    otp_code = serializers.CharField(
        max_length=6, required=False, write_only=True, allow_blank=True)

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
        
        # Enforce Withdrawal Limits
        sender = attrs["sender_account"]
        amount = attrs.get("amount", Decimal("0"))
        
        if amount > sender.maximum_withdrawal_amount:
            raise serializers.ValidationError({
                "amount": f"Amount exceeds the maximum limit of {sender.maximum_withdrawal_amount} for this account type."
            })

        # OTP validation for high-value transfers
        amount = attrs.get("amount", Decimal("0"))
        if amount > HIGH_VALUE_TRANSFER_THRESHOLD:
            otp_code = attrs.get("otp_code", "").strip()
            if not otp_code:
                raise serializers.ValidationError({
                    "otp_code": f"OTP required for amounts > {HIGH_VALUE_TRANSFER_THRESHOLD}"
                })
            
            # Verify OTP
            req = self.context.get("request")
            if not req or not req.user:
                raise serializers.ValidationError("Authentication required.")
            
            if not OTPVerification.verify_code(
                req.user, otp_code, OTPVerification.Purpose.TRANSACTION
            ):
                raise serializers.ValidationError({
                    "otp_code": "Invalid or expired OTP code."
                })
        
        return attrs

    def create(self, validated):
        idem = validated.get("idempotency_key") or None
        existing = (Transaction.objects.filter(
            idempotency_key=idem).first() if idem else None)
        self.created = existing is None
        if existing:
            return existing
        tx = Transaction.objects.create(
            sender_account=validated["sender_account"],
            receiver_account=validated["receiver_account"],
            amount=validated["amount"],
            idempotency_key=idem,
            fee_amount=Decimal("0.00"),
            status=Transaction.Status.SUCCESS,
        )
        return tx


class ExternalTransferSerializer(serializers.Serializer):
    """
    Transfer from one of the user's accounts to another user's account_number.
    Sender queryset is restricted per-request; receiver is looked up by number.
    OTP required for amounts > 500.
    """

    sender_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    receiver_account_number = serializers.CharField(max_length=12)
    amount = serializers.DecimalField(max_digits=12,
                                      decimal_places=2,
                                      min_value=Decimal("0.01"))
    idempotency_key = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True)
    otp_code = serializers.CharField(
        max_length=6, required=False, write_only=True, allow_blank=True)

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
        
        # Enforce Withdrawal Limits
        amount = attrs.get("amount", Decimal("0"))
        if amount > sender.maximum_withdrawal_amount:
            raise serializers.ValidationError({
                "amount": f"Amount exceeds the maximum limit of {sender.maximum_withdrawal_amount} for this account type."
            })

        attrs["receiver_account"] = receiver
        
        # OTP validation for high-value transfers
        amount = attrs.get("amount", Decimal("0"))
        if amount > HIGH_VALUE_TRANSFER_THRESHOLD:
            otp_code = attrs.get("otp_code", "").strip()
            if not otp_code:
                raise serializers.ValidationError({
                    "otp_code": f"OTP required for amounts > {HIGH_VALUE_TRANSFER_THRESHOLD}"
                })
            
            # Verify OTP
            req = self.context.get("request")
            if not req or not req.user:
                raise serializers.ValidationError("Authentication required.")
            
            if not OTPVerification.verify_code(
                req.user, otp_code, OTPVerification.Purpose.TRANSACTION
            ):
                raise serializers.ValidationError({
                    "otp_code": "Invalid or expired OTP code."
                })
        
        return attrs

    def create(self, validated):
        idem = validated.get("idempotency_key") or None
        existing = (Transaction.objects.filter(
            idempotency_key=idem).first() if idem else None)
        self.created = existing is None
        if existing:
            return existing
        # Calculate Fee (1% for external transfers)
        amount = validated["amount"]
        fee_amount = (amount * EXTERNAL_TRANSFER_FEE_PERCENTAGE).quantize(Decimal("0.01"))

        tx = Transaction.objects.create(
            sender_account=validated["sender_account"],
            receiver_account=validated["receiver_account"],
            amount=amount,
            idempotency_key=idem,
            fee_amount=fee_amount,
            status=Transaction.Status.SUCCESS,
        )
        return tx


class BillPaymentSerializer(serializers.ModelSerializer):
    """
    Create/list bill payments for the authenticated user.
    User is injected via HiddenField; account queryset is user-scoped.
    Supports idempotency_key for double-submit prevention.
    """

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.none())
    idempotency_key = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True)

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
            "idempotency_key",
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

    def create(self, validated_data):
        # Check for existing payment with same idempotency_key
        idem = validated_data.get("idempotency_key") or None
        if idem:
            existing = BillPayment.objects.filter(idempotency_key=idem).first()
            if existing:
                self.created = False
                return existing  # Return existing payment, no duplicate

        self.created = True
        bill_payment = super().create(validated_data)
        # Immediately settle the bill; pay() will raise on insufficient funds.
        bill_payment.pay()
        return bill_payment


class BillerSerializer(serializers.ModelSerializer):
    """Public read serializer for billers."""

    class Meta:
        model = Biller
        fields = ("id", "name", "fixed_amount")
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for user notifications.
    Returns notification history ordered by newest first.
    """

    class Meta:
        model = Notification
        fields = [
            "id",
            "message",
            "notification_type",
            "is_read",
            "related_transaction",
            "created_at",
        ]
        read_only_fields = fields


# =============================================================================
# TWO-FACTOR AUTHENTICATION SERIALIZERS
# =============================================================================


class LoginStepOneSerializer(serializers.Serializer):
    """
    Serializer for Step 1 of 2FA Login.
    Validates email and password input for credential verification.
    """
    email = serializers.EmailField(
        help_text="User's email address"
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="User's password"
    )


class LoginStepTwoSerializer(serializers.Serializer):
    """
    Serializer for Step 2 of 2FA Login.
    Validates email and OTP code for verification.
    """
    email = serializers.EmailField(
        help_text="User's email address"
    )
    code = serializers.CharField(
        max_length=6,
        min_length=6,
        help_text="6-digit OTP code sent via email"
    )


class TokenResponseSerializer(serializers.Serializer):
    """
    Response serializer for JWT token pair.
    Used for Swagger documentation of login response.
    """
    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")


class OTPSentResponseSerializer(serializers.Serializer):
    """
    Response serializer for OTP generation endpoints.
    """
    detail = serializers.CharField(help_text="Status message")


