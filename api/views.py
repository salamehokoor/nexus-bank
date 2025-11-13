from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from django.db.models import Count
from .models import Account, Card
from .serializers import AccountSerializer, CardSerializer
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from rest_framework.response import Response
from rest_framework import generics, permissions, status, viewsets
from django.db.models import Count, Q
from .models import Account, Card, User, Transaction, BillPayment
from .serializers import AccountSerializer, CardSerializer, InternalTransferSerializer, UserSerializer, ExternalTransferSerializer, TransactionSerializer, BillPaymentSerializer
from rest_framework.views import APIView
from djoser.serializers import ActivationSerializer as UserActivationSerializer
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator

#class GoogleLogin(SocialLoginView):
#   adapter_class = GoogleOAuth2Adapter

#User = get_user_model()

#class ActivateUserView(APIView):
#    permission_classes = [permissions.AllowAny]

# def get(self, request, uid, token, *args, **kwargs):
#    try:
# Djoser encodes the user id as base64
#       uid_str = urlsafe_base64_decode(uid).decode()
#      user = User.objects.get(pk=uid_str)
# except (TypeError, ValueError, OverflowError, User.DoesNotExist,
#        UnicodeDecodeError):
#   return Response(
#      {"detail": "Invalid activation link."},
#     status=status.HTTP_400_BAD_REQUEST,
#)

# Check the token using Django's default token generator
#if not default_token_generator.check_token(user, token):
#   return Response(
#      {"detail": "Invalid or expired activation token."},
#     status=status.HTTP_400_BAD_REQUEST,
#)

# Mark user as active
#if not user.is_active:
#   user.is_active = True
#  user.save(update_fields=["is_active"])

# Redirect to your frontend (success page)
#return redirect("http://localhost:3000/auth/users/activation")


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
    GET  /accounts/<account_number>/cards/  -> list cards for that account
    POST /accounts/<account_number>/cards/  -> create a card for that account
    """
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        acct_num = self.kwargs["account_number"]
        get_object_or_404(Account,
                          account_number=acct_num,
                          user=self.request.user)
        return Card.objects.filter(account_id=acct_num).order_by("-created_at")
        # return only cards linked to that account

    def perform_create(self, serializer):
        acct_num = self.kwargs["account_number"]
        account = get_object_or_404(Account,
                                    account_number=acct_num,
                                    user=self.request.user)
        serializer.save(account=account)


class InternalTransferListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/transfers/internal/     -> list internal transfers (mine -> mine)
    POST /api/transfers/internal/     -> create internal transfer
    """
    permission_classes = [permissions.IsAuthenticated]

    # POST uses the input serializer; GET uses the read serializer
    def get_serializer_class(self):
        return InternalTransferSerializer if self.request.method == "POST" else TransactionSerializer

    def get_queryset(self):
        u = self.request.user
        qs = Transaction.objects.filter(
            sender_account__user=u,
            receiver_account__user=u,
        )
        # optional filters
        account_number = self.request.query_params.get("account_number")
        if account_number:
            qs = qs.filter(
                Q(sender_account_number=account_number)
                | Q(receiver_account_number=account_number))
        date_from = self.request.query_params.get("from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = self.request.query_params.get("to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        ordering = self.request.query_params.get("ordering")
        return qs.order_by(ordering) if ordering in (
            "created_at", "-created_at", "amount",
            "-amount") else qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        tx = s.save()
        return Response(TransactionSerializer(tx, context={
            "request": request
        }).data,
                        status=status.HTTP_201_CREATED)


class ExternalTransferListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/transfers/external/     -> list outgoing external transfers (mine -> others)
    POST /api/transfers/external/     -> create external transfer
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return ExternalTransferSerializer if self.request.method == "POST" else TransactionSerializer

    def get_queryset(self):
        u = self.request.user
        qs = Transaction.objects.filter(sender_account__user=u).exclude(
            receiver_account__user=u)
        # optional filters
        sender_id = self.request.query_params.get("sender_id")
        if sender_id:
            qs = qs.filter(sender_account_number=sender_id)
        date_from = self.request.query_params.get("from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = self.request.query_params.get("to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        ordering = self.request.query_params.get("ordering")
        return qs.order_by(ordering) if ordering in (
            "created_at", "-created_at", "amount",
            "-amount") else qs.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        tx = s.save()
        return Response(TransactionSerializer(tx, context={
            "request": request
        }).data,
                        status=status.HTTP_201_CREATED)


class BillPaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = BillPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        #get the value of this attribute if it exists, otherwise return a default value.
        if not getattr(user, "is_authenticated", False):
            return BillPayment.objects.none()
        return BillPayment.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save()  # user is injected by the serializer


class BillPaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BillPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        #get the value of this attribute if it exists, otherwise return a default value.
        if not getattr(user, "is_authenticated", False):
            return BillPayment.objects.none()
        return BillPayment.objects.filter(user=user)
