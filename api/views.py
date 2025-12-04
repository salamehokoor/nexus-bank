from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from .models import Account, Card
from .serializers import AccountSerializer, CardSerializer
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Transaction, BillPayment
from .serializers import InternalTransferSerializer, ExternalTransferSerializer, TransactionSerializer, BillPaymentSerializer
from django.shortcuts import redirect
from rest_framework_simplejwt.tokens import RefreshToken
from risk.transaction_logging import (
    log_transaction_event,
    log_failed_transfer_attempt,
)
from rest_framework.exceptions import ValidationError
from django.contrib.auth import get_user_model
from rest_framework.views import APIView

User = get_user_model()


def social_login_complete(request):
    """
    Called after allauth finishes Google login.
    request.user is already authenticated at this point.
    We generate JWTs and redirect to the frontend with them.
    """
    if not request.user.is_authenticated:
        return redirect(
            f"{settings.FRONTEND_URL}/auth/social/error?reason=not_authenticated"
        )

    refresh = RefreshToken.for_user(request.user)
    access = str(refresh.access_token)

    redirect_url = (f"{settings.FRONTEND_URL}/auth/social/success"
                    f"?access={access}&refresh={refresh}")
    return redirect(redirect_url)


###
class LogoutView(APIView):
    schema = None  # avoid schema guess issues in docs
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Mark offline
        User.objects.filter(pk=request.user.pk).update(is_online=False)

        # OPTIONAL: Blacklist refresh token
        # Only if using JWT blacklist:
        # request.auth.blacklist()

        return Response({"detail": "Logged out successfully."})


##
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
        try:
            s.is_valid(raise_exception=True)
            tx = s.save()
        except ValidationError as exc:
            log_failed_transfer_attempt(
                request=request,
                user=request.user,
                errors=exc.detail,
                amount=request.data.get("amount"),
                receiver_account=request.data.get("receiver_account"),
            )
            raise

        # 🔥 send this transfer to the risk engine
        log_transaction_event(request=request, user=request.user, transaction=tx)

        return Response(
            TransactionSerializer(tx, context={
                "request": request
            }).data,
            status=status.HTTP_201_CREATED,
        )


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
        try:
            s.is_valid(raise_exception=True)
            tx = s.save()
        except ValidationError as exc:
            log_failed_transfer_attempt(
                request=request,
                user=request.user,
                errors=exc.detail,
                amount=request.data.get("amount"),
                receiver_account=request.data.get("receiver_account"),
            )
            raise

        # 🔥 also evaluate external transfers for high-value risk
        log_transaction_event(request=request, user=request.user, transaction=tx)

        return Response(
            TransactionSerializer(tx, context={
                "request": request
            }).data,
            status=status.HTTP_201_CREATED,
        )


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
