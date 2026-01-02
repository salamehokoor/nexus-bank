"""
API routes for accounts, cards, transfers, bill payments, notifications, 2FA auth, and social auth.
"""
from django.urls import path
from .views import (
    AccountCardsListCreateView,
    AccountsListCreateView,
    BillPaymentDetailView,
    BillPaymentListCreateView,
    ExternalTransferListCreateView,
    GenerateTransactionOTPView,
    InternalTransferListCreateView,
    LoginInitView,
    LoginVerifyView,
    NotificationListView,
    NotificationMarkReadView,
    social_login_complete,
)
from .views import BillerListView

urlpatterns = [
    path("accounts", AccountsListCreateView.as_view(), name="accounts-list"),
    ###
    path("accounts/<str:account_number>/cards/",
         AccountCardsListCreateView.as_view(),
         name="account-cards"),
    ###
    path("auth/social/complete/",
         social_login_complete,
         name="social-login-complete"),
    ###
    # 2FA Authentication
    path("auth/login/init/", LoginInitView.as_view(), name="login-init"),
    path("auth/login/verify/", LoginVerifyView.as_view(), name="login-verify"),
    path("auth/otp/generate/", GenerateTransactionOTPView.as_view(), name="otp-generate"),
    ###
    path("transfers/internal/",
         InternalTransferListCreateView.as_view(),
         name="transfer-internal"),
    ###
    path("transfers/external/",
         ExternalTransferListCreateView.as_view(),
         name="transfer-external"),
    ###
    path("bill/", BillPaymentListCreateView.as_view(), name="bill-list"),
    ###
    path("bill/<int:pk>/", BillPaymentDetailView.as_view(),
         name="bill-detail"),
    ###
    path("billers/", BillerListView.as_view(), name="billers"),
    ###
    # Notifications REST API
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
]


