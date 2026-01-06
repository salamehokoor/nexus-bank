from decimal import Decimal

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
from .models import Account, BillPayment, Card, Notification, OTPVerification, Transaction, TransferOTP
from .serializers import (
    AccountSerializer,
    BillPaymentSerializer,
    CardSerializer,
    CardUpdateSerializer,
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


class CardDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /cards/<id>/         -> Retrieve card details
    PATCH /cards/<id>/       -> Update card (e.g. freeze/unfreeze)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return CardUpdateSerializer
        return CardSerializer

    def get_queryset(self):
        # Allow access only to cards owned by one of the user's accounts
        return Card.objects.filter(account__user=self.request.user)


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
            
            # Use Decimal here now that it is imported
            amount = serializer.validated_data.get("amount", Decimal("0.00"))
            
            # Determine logic based on status
            is_high_value = amount > Decimal("500.00")
            initial_status = Transaction.Status.PENDING_OTP if is_high_value else Transaction.Status.SUCCESS

            try:
                tx = serializer.save(status=initial_status)
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

        # OTP Handling for High Value
        if is_high_value:
            # Generate OTP & Send Email
            auth_otp, raw_code = TransferOTP.generate(request.user, tx)
            
            send_mail(
                subject="Nexus Bank - Confirm Your Transfer",
                message=f"Your transfer verification code is: {raw_code}\n\n"
                        f"Amount: {amount}\n"
                        f"This code expires in 5 minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )
            
            return Response(
                {
                    "otp_required": True, 
                    "transfer_id": str(tx.id),
                    "message": "OTP sent to email. Please verify to complete transfer."
                },
                status=status.HTTP_200_OK,
            )

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
            
            amount = serializer.validated_data.get("amount", Decimal("0.00"))
            is_high_value = amount > Decimal("500.00")
            initial_status = Transaction.Status.PENDING_OTP if is_high_value else Transaction.Status.SUCCESS

            try:
                tx = serializer.save(status=initial_status)
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

        if is_high_value:
             # Generate OTP & Send Email
            auth_otp, raw_code = TransferOTP.generate(request.user, tx)
            
            send_mail(
                subject="Nexus Bank - Confirm Your Transfer",
                message=f"Your transfer verification code is: {raw_code}\n\n"
                        f"Amount: {amount}\n"
                        f"This code expires in 5 minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )
            
            return Response(
                {
                    "otp_required": True, 
                    "transfer_id": str(tx.id),
                    "message": "OTP sent to email. Please verify to complete transfer."
                },
                status=status.HTTP_200_OK,
            )

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
    PATCH/POST /notifications/<pk>/read/
    Marks a specific notification as read.
    Accepts both PATCH and POST methods for frontend compatibility.
    
    If the notification doesn't exist (e.g., client-generated ID), returns 204 No Content
    to indicate the operation completed (nothing to mark as read).
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def patch(self, request, *args, **kwargs):
        pk = kwargs.get("pk")
        
        # Try to find the notification
        try:
            # First, attempt to convert pk to integer for proper lookup
            # since our Notification model uses integer PKs
            try:
                pk_int = int(pk)
            except (ValueError, TypeError):
                # Non-numeric ID (e.g., client-generated UUID) - doesn't exist in backend
                return Response(status=status.HTTP_204_NO_CONTENT)
            
            notification = self.get_queryset().get(pk=pk_int)
        except Notification.DoesNotExist:
            # Notification doesn't exist - treat as "already marked as read"
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        # Mark as read
        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])
        return Response(self.get_serializer(notification).data)

    def post(self, request, *args, **kwargs):
        """Accept POST as an alias for PATCH for frontend compatibility."""
        return self.patch(request, *args, **kwargs)


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


class TransferConfirmationView(APIView):
    """
    POST /transfers/confirm/
    Confirm a Pending Transfer using OTP.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Confirm Pending Transfer",
        description="Verify OTP for a high-value pending transfer and execute it.",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "transfer_id": {"type": "integer"},
                    "otp": {"type": "string"},
                },
                "required": ["transfer_id", "otp"],
            }
        },
        responses={
            200: TransactionSerializer,
            400: OpenApiResponse(description="Invalid OTP or Transfer ID"),
            423: OpenApiResponse(description="OTP Limit Reached"),
        }
    )
    def post(self, request):
        transfer_id = request.data.get("transfer_id")
        otp_code = request.data.get("otp")

        if not transfer_id or not otp_code:
            return Response({"detail": "Missing transfer_id or otp."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Get Transaction
        # Check permissions: must belong to user
        tx = get_object_or_404(Transaction, pk=transfer_id, sender_account__user=request.user)
        
        if tx.status != Transaction.Status.PENDING_OTP:
            return Response({"detail": "This transfer is not pending OTP."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Get OTP
        try:
            transfer_otp = tx.otp_request
        except TransferOTP.DoesNotExist:
            return Response({"detail": "No OTP found for this transfer."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Verify
        # Check lock status first
        if transfer_otp.attempts >= TransferOTP.MAX_ATTEMPTS:
             return Response({"detail": "Too many failed attempts. Transfer locked."}, status=status.HTTP_423_LOCKED)

        if not transfer_otp.verify(otp_code):
             return Response({
                 "detail": "Invalid or expired OTP.",
                 "attempts_left": TransferOTP.MAX_ATTEMPTS - transfer_otp.attempts
             }, status=status.HTTP_400_BAD_REQUEST)

        # 4. Execute Transfer
        try:
            # Mark OTP as used
            transfer_otp.is_used = True
            transfer_otp.save(update_fields=['is_used'])
            
            # Update Status and Execute
            tx.status = Transaction.Status.SUCCESS
            tx.execute_transaction()
            
            return Response(TransactionSerializer(tx).data, status=status.HTTP_200_OK)

        except ValueError as e:
            # e.g. Unsufficient funds since PENDING state (unlikely but possible)
            tx.status = Transaction.Status.FAILED
            tx.save(update_fields=['status'])
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
