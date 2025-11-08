from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from django.db.models import Count
from .models import Account, Card
from .serializers import AccountSerializer, CardSerializer
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter


class AccountsListCreateView(generics.ListCreateAPIView):
    """
    GET /accounts
    POST /accounts
    """
    serializer_class = AccountSerializer

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Account.objects.filter(user=self.request.user)

        acc_type = self.request.query_params.get("type")
        if acc_type:
            qs = qs.filter(type=acc_type)
        #GET /accounts?type=Savings --> Lists only savings accounts

        ordering = self.request.query_params.get("ordering")
        if ordering in ("balance", "-balance", "created_at", "-created_at"):
            qs = qs.order_by(ordering)
        else:
            # default ordering: newest to oldest
            qs = qs.order_by("-created_at")
        #GET /accounts?ordering=-balance --> Lists all accounts sorted by balance descending

        return qs

    def perform_create(self, serializer):
        # Force ownership to the authenticated user (ignore any user sent by client)
        serializer.save(user=self.request.user)


class AccountCardsListCreateView(generics.ListCreateAPIView):
    """
    GET  /accounts/<uuid:account_id>/cards/  -> list cards for that account
    POST /accounts/<uuid:account_id>/cards/  -> create a card for that account
    """
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        account_id = self.kwargs["account_id"]
        # verify that the account belongs to the current user
        get_object_or_404(Account, id=account_id, user=self.request.user)
        # return only cards linked to that account
        return Card.objects.filter(
            account_id=account_id).order_by("-created_at")

    def perform_create(self, serializer):
        # automatically attach the card to the correct account and user
        account = get_object_or_404(Account,
                                    id=self.kwargs["account_id"],
                                    user=self.request.user)
        serializer.save(account=account)
