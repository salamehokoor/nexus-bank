"""
Admin registrations for core banking models.
Provides quick search/filter for users, accounts, cards, and payments.
"""

from django.contrib import admin
from .models import (
    User,
    UserProfile,
    UserAddress,
    Account,
    Card,
    Transaction,
    Biller,
    BillPayment,
)

admin.site.site_header = "Nexus Admin"
admin.site.site_title = "Nexus Admin Portal"
admin.site.index_title = "Dashboard"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "is_staff", "is_superuser", "is_active")
    search_fields = ("email",)
    ordering = ("-date_joined",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "first_name", "last_name", "birth_date")
    search_fields = ("user__email", "first_name", "last_name")


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "street", "city", "created_at")
    search_fields = ("user__email", "street", "city")
    list_filter = ("city",)
    ordering = ("-created_at",)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("account_number", "user", "type", "currency", "balance",
                    "is_active", "created_at")
    search_fields = ("account_number", "user__email")
    list_filter = ("type", "currency", "is_active")
    ordering = ("-created_at",)


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("card_number", "account", "card_type", "is_active",
                    "expiration_date")
    search_fields = ("card_number", "account__account_number",
                     "account__user__email")
    list_filter = ("card_type", "is_active")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "sender_account", "receiver_account", "amount",
                    "created_at")
    search_fields = ("sender_account__account_number",
                     "receiver_account__account_number",
                     "sender_account__user__email",
                     "receiver_account__user__email")
    ordering = ("-created_at",)


@admin.register(Biller)
class BillerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "fixed_amount")
    search_fields = ("name",)
    list_filter = ("category",)


@admin.register(BillPayment)
class BillPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "account", "biller", "reference_number",
                    "amount", "currency", "status", "created_at")
    search_fields = ("reference_number", "user__email", "account__account_number")
    list_filter = ("status", "currency", "biller")
    ordering = ("-created_at",)
