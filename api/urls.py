# api/urls.py

from django.urls import path
from .views import AccountsListCreateView, AccountCardsListCreateView
from .views import GoogleLogin
from .views import GoogleLogin
from .views import AccountsListCreateView, AccountCardsListCreateView, InternalTransferListCreateView, ExternalTransferListCreateView

urlpatterns = [
    path("accounts", AccountsListCreateView.as_view(), name="accounts-list"),
    path("accounts/<str:account_number>/cards/",
         AccountCardsListCreateView.as_view(),
         name="account-cards"),
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path("transfers/internal/",
         InternalTransferListCreateView.as_view(),
         name="transfer-internal"),
    path("transfers/external/",
         ExternalTransferListCreateView.as_view(),
         name="transfer-external"),
]
