# api/urls.py

from django.urls import path
from .views import AccountsListCreateView, AccountCardsListCreateView

urlpatterns = [
    path("accounts", AccountsListCreateView.as_view(), name="accounts-list"),
    path("accounts/<uuid:account_id>/cards/",
         AccountCardsListCreateView.as_view(),
         name="account-cards"),
]
