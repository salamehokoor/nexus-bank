from django.urls import path
from .views import AccountsListCreateView, AccountCardsListCreateView
from .views import InternalTransferListCreateView, ExternalTransferListCreateView, BillPaymentListCreateView, BillPaymentDetailView, social_login_complete

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
]
