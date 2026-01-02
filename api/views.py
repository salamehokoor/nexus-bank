"""
API views for accounts, cards, transfers, bill payments, notifications, 2FA auth, and social login.
All endpoints enforce authentication and ownership scoping where applicable.
"""

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from risk.transaction_logging import (
    log_failed_transfer_attempt,
    log_transaction_event,
)
from .models import Account, BillPayment, Card, Notification, OTPVerification, Transaction
from .serializers import (
    AccountSerializer,
    BillPaymentSerializer,
    CardSerializer,
    ExternalTransferSerializer,
    InternalTransferSerializer,
    LoginStepOneSerializer,
    LoginStepTwoSerializer,
    NotificationSerializer,
    OTPSentResponseSerializer,
    TokenResponseSerializer,
    TransactionSerializer,
)

User = get_user_model()

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


class LogoutView(APIView):
    """Mark the user offline and end the session context."""

    schema = None  # avoid schema guess issues in docs
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        User.objects.filter(pk=request.user.pk).update(is_online=False)
        return Response({"detail": "Logged out successfully."})


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

        ordering = self.request.query_params.get("ordering")
        if ordering in ("balance", "-balance", "created_at", "-created_at"):
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs

    def perform_create(self, serializer):
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

    def get_serializer_class(self):
        return (InternalTransferSerializer
                if self.request.method == "POST" else TransactionSerializer)

    def get_queryset(self):
        u = self.request.user
        qs = Transaction.objects.filter(
            sender_account__user=u,
            receiver_account__user=u,
        )
        account_number = self.request.query_params.get("account_number")
        if account_number:
            qs = qs.filter(
                Q(sender_account__account_number=account_number)
                | Q(receiver_account__account_number=account_number))
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
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            try:
                tx = serializer.save()
            except ValueError as exc:
                raise ValidationError({"detail": str(exc)})
        except ValidationError as exc:
            log_failed_transfer_attempt(
                request=request,
                user=request.user,
                errors=exc.detail,
                amount=request.data.get("amount"),
                receiver_account=request.data.get("receiver_account"),
            )
            raise

        if getattr(serializer, "created", True):
            log_transaction_event(request=request,
                                  user=request.user,
                                  transaction=tx)

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
        return (ExternalTransferSerializer
                if self.request.method == "POST" else TransactionSerializer)

    def get_queryset(self):
        u = self.request.user
        qs = Transaction.objects.filter(sender_account__user=u).exclude(
            receiver_account__user=u)
        sender_id = self.request.query_params.get("sender_id")
        if sender_id:
            qs = qs.filter(sender_account__account_number=sender_id)
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
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            try:
                tx = serializer.save()
            except ValueError as exc:
                raise ValidationError({"detail": str(exc)})
        except ValidationError as exc:
            log_failed_transfer_attempt(
                request=request,
                user=request.user,
                errors=exc.detail,
                amount=request.data.get("amount"),
                receiver_account=request.data.get("receiver_account"),
            )
            raise

        if getattr(serializer, "created", True):
            log_transaction_event(request=request,
                                  user=request.user,
                                  transaction=tx)

        return Response(
            TransactionSerializer(tx, context={
                "request": request
            }).data,
            status=status.HTTP_201_CREATED,
        )


class BillPaymentListCreateView(generics.ListCreateAPIView):
    """List/create bill payments for the authenticated user."""

    serializer_class = BillPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return BillPayment.objects.none()
        return BillPayment.objects.filter(user=user)

    def perform_create(self, serializer):
        try:
            serializer.save()
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})


class BillPaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve/update/delete a specific bill payment owned by the user."""

    serializer_class = BillPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return BillPayment.objects.none()
        return BillPayment.objects.filter(user=user)


class BillerListView(generics.ListAPIView):
    """Read-only list of billers for discovery."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BillPaymentSerializer  # placeholder to satisfy DRF, replaced below

    def get_serializer_class(self):
        from .serializers import BillerSerializer
        return BillerSerializer

    def get_queryset(self):
        from .models import Biller
        return Biller.objects.all().order_by("name")


class NotificationListView(generics.ListAPIView):
    """
    GET /notifications/
    Returns all notifications for the authenticated user, newest first.
    Supports ?unread_only=true to filter unread notifications.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        
        # Optional filter for unread only
        if self.request.query_params.get("unread_only", "").lower() == "true":
            qs = qs.filter(is_read=False)
        
        # Filter by notification type if provided
        notification_type = self.request.query_params.get("type")
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
        
        return qs.order_by("-created_at")


class NotificationMarkReadView(generics.UpdateAPIView):
    """
    PATCH /notifications/<pk>/read/
    Marks a specific notification as read.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def patch(self, request, *args, **kwargs):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])
        return Response(self.get_serializer(notification).data)


# =============================================================================
# TWO-FACTOR AUTHENTICATION VIEWS
# =============================================================================


class LoginInitView(APIView):
    """
    Step 1 of 2FA Login: Validate credentials and send OTP via email.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Step 1: Login Initialization",
        description="Validate email/password credentials and send OTP code via email. "
                    "This is the first step of the 2FA login flow.",
        request=LoginStepOneSerializer,
        responses={
            200: OTPSentResponseSerializer,
            400: OpenApiResponse(description="Missing email or password"),
            401: OpenApiResponse(description="Invalid credentials or disabled account"),
        },
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginStepOneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        # Authenticate user with credentials
        user = authenticate(request, email=email, password=password)
        
        if user is None:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "Account is disabled."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Generate LOGIN OTP
        otp = OTPVerification.generate(user, OTPVerification.Purpose.LOGIN)

        # Send OTP via email
        send_mail(
            subject="Nexus Bank - Login Verification Code",
            message=f"Your login verification code is: {otp.code}\n\nThis code expires in 5 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {"detail": "OTP sent to email"},
            status=status.HTTP_200_OK,
        )



class LoginVerifyView(APIView):
    """
    Step 2 of 2FA Login: Verify OTP and return JWT tokens.
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Step 2: Login Verification",
        description="Verify the OTP code sent via email and return JWT access/refresh tokens. "
                    "This completes the 2FA login flow.",
        request=LoginStepTwoSerializer,
        responses={
            200: TokenResponseSerializer,
            400: OpenApiResponse(description="Missing email or code"),
            401: OpenApiResponse(description="Invalid email, code, or expired OTP"),
        },
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginStepTwoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        code = serializer.validated_data["code"].strip()

        # Find the user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or code."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Verify OTP code
        if not OTPVerification.verify_code(user, code, OTPVerification.Purpose.LOGIN):
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Mark user as online
        User.objects.filter(pk=user.pk).update(is_online=True)

        # Generate JWT tokens - explicitly converting to string
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })


class GenerateTransactionOTPView(APIView):
    """
    Generate OTP for high-value transaction authorization (amounts > 500).
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Generate Transaction OTP",
        description="Request an OTP code for authorizing high-value transfers (> 500). "
                    "The code is sent to the authenticated user's email.",
        request=None,
        responses={
            200: OTPSentResponseSerializer,
            401: OpenApiResponse(description="Authentication required"),
        },
        tags=["Authentication"],
    )
    def post(self, request):
        user = request.user

        # Generate TRANSACTION OTP
        otp = OTPVerification.generate(user, OTPVerification.Purpose.TRANSACTION)

        # Send OTP via email
        send_mail(
            subject="Nexus Bank - Transaction Authorization Code",
            message=f"Your transaction authorization code is: {otp.code}\n\nThis code expires in 5 minutes.\n\nIf you did not request this code, please contact support immediately.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {"detail": "OTP sent to email"},
            status=status.HTTP_200_OK,
        )
