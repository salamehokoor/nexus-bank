from rest_framework import serializers
from .models import Account, Card, User


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User

        fields = ("id", 'first_name', 'email', 'is_staff', 'is_superuser')


class CardSerializer(serializers.ModelSerializer):
    last4 = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = ["id", "card_type", "last4", "is_active", "expiration_date"]

    def get_last4(self, obj):
        return obj.card_number[-4:]


class AccountSerializer(serializers.ModelSerializer):
    mask = serializers.SerializerMethodField()
    maximum_withdrawal_amount = serializers.DecimalField(max_digits=12,
                                                         decimal_places=2,
                                                         read_only=True)
    card_count = serializers.SerializerMethodField()

    owner = UserSerializer(source="user", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "account_number",
            "owner",
            "mask",
            "type",
            "balance",
            "is_active",
            "maximum_withdrawal_amount",
            "card_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "account_number", "owner", "mask",
                            "is_active", "maximum_withdrawal_amount",
                            "card_count", "created_at", "updated_at")

    def get_mask(self, obj):
        n = len(obj.account_number)
        return f"{'*' * (n - 4)}{obj.account_number[-4:]}"

    def get_card_count(self, obj):
        return obj.cards.count()
