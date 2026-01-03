"""
Admin Response API views (Scope 1.5.7).

Provides admin-only endpoints to:
- Block/Unblock users
- Freeze/Unfreeze accounts
- Terminate user sessions (blacklist tokens)

All actions are logged to the Incident model for audit compliance.
"""
import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import User, Account
from risk.models import Incident

logger = logging.getLogger(__name__)


def _log_admin_action(admin_user, action: str, target_type: str, target_id, details: dict = None):
    """
    Create an Incident record for admin actions (audit trail).
    """
    Incident.objects.create(
        user=admin_user,
        event=f"Admin Action: {action}",
        severity="medium",
        ip="",  # Could be extracted from request if needed
        country="",
        details={
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "performed_by": admin_user.email,
            "timestamp": timezone.now().isoformat(),
            **(details or {}),
        },
    )
    logger.info(f"Admin {admin_user.email} performed {action} on {target_type}:{target_id}")


# --------------------------------------------------------------------------
# User Block/Unblock Endpoints
# --------------------------------------------------------------------------
class AdminUserBlockView(APIView):
    """
    POST /admin/users/<id>/block/
    Block a user by setting is_active=False.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        description="Block a user (set is_active=False). Logs the action for audit.",
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        if not user.is_active:
            return Response(
                {"detail": f"User {user.email} is already blocked."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Block user
        user.is_active = False
        user.save(update_fields=["is_active"])
        
        # Audit log
        _log_admin_action(
            admin_user=request.user,
            action="BLOCK_USER",
            target_type="User",
            target_id=pk,
            details={"user_email": user.email}
        )
        
        return Response({"detail": f"User {user.email} has been blocked."})


class AdminUserUnblockView(APIView):
    """
    POST /admin/users/<id>/unblock/
    Unblock a user by setting is_active=True.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        description="Unblock a user (set is_active=True). Logs the action for audit.",
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        if user.is_active:
            return Response(
                {"detail": f"User {user.email} is already active."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Unblock user
        user.is_active = True
        user.save(update_fields=["is_active"])
        
        # Audit log
        _log_admin_action(
            admin_user=request.user,
            action="UNBLOCK_USER",
            target_type="User",
            target_id=pk,
            details={"user_email": user.email}
        )
        
        return Response({"detail": f"User {user.email} has been unblocked."})


# --------------------------------------------------------------------------
# Account Freeze/Unfreeze Endpoints
# --------------------------------------------------------------------------
class AdminAccountFreezeView(APIView):
    """
    POST /admin/accounts/<account_number>/freeze/
    Freeze an account by setting is_active=False.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        description="Freeze an account (set is_active=False). Logs the action for audit.",
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request, account_number):
        account = get_object_or_404(Account, account_number=account_number)
        
        if not account.is_active:
            return Response(
                {"detail": f"Account {account_number} is already frozen."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Freeze account
        account.is_active = False
        account.save(update_fields=["is_active"])
        
        # Audit log
        _log_admin_action(
            admin_user=request.user,
            action="FREEZE_ACCOUNT",
            target_type="Account",
            target_id=account_number,
            details={"owner_email": account.user.email}
        )
        
        return Response({"detail": f"Account {account_number} has been frozen."})


class AdminAccountUnfreezeView(APIView):
    """
    POST /admin/accounts/<account_number>/unfreeze/
    Unfreeze an account by setting is_active=True.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        description="Unfreeze an account (set is_active=True). Logs the action for audit.",
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request, account_number):
        account = get_object_or_404(Account, account_number=account_number)
        
        if account.is_active:
            return Response(
                {"detail": f"Account {account_number} is already active."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Unfreeze account
        account.is_active = True
        account.save(update_fields=["is_active"])
        
        # Audit log
        _log_admin_action(
            admin_user=request.user,
            action="UNFREEZE_ACCOUNT",
            target_type="Account",
            target_id=account_number,
            details={"owner_email": account.user.email}
        )
        
        return Response({"detail": f"Account {account_number} has been unfrozen."})


# --------------------------------------------------------------------------
# Session Termination (Token Blacklist)
# --------------------------------------------------------------------------
class AdminTerminateSessionView(APIView):
    """
    POST /admin/users/<id>/terminate-session/
    Invalidate all refresh tokens for a user.
    
    Requires 'rest_framework_simplejwt.token_blacklist' in INSTALLED_APPS.
    If not installed, returns a warning but still logs the action.
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        description="Terminate all active sessions for a user by blacklisting their refresh tokens.",
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        
        tokens_blacklisted = 0
        
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            
            # Get all outstanding tokens for this user
            outstanding_tokens = OutstandingToken.objects.filter(user=user)
            
            for token in outstanding_tokens:
                # Blacklist each token (if not already blacklisted)
                BlacklistedToken.objects.get_or_create(token=token)
                tokens_blacklisted += 1
            
        except ImportError:
            # token_blacklist not installed
            logger.warning(
                "Token blacklist not available. Install 'rest_framework_simplejwt.token_blacklist' "
                "and run migrations to enable token revocation."
            )
            
            # Still proceed with audit log
            _log_admin_action(
                admin_user=request.user,
                action="TERMINATE_SESSION_ATTEMPTED",
                target_type="User",
                target_id=pk,
                details={
                    "user_email": user.email,
                    "warning": "Token blacklist not installed",
                }
            )
            
            return Response({
                "detail": f"Session termination recorded for {user.email}. "
                          f"Note: Token blacklist not configured - tokens may still be valid until expiry.",
                "warning": "Install token_blacklist for full token revocation support."
            })
        
        # Audit log
        _log_admin_action(
            admin_user=request.user,
            action="TERMINATE_SESSION",
            target_type="User",
            target_id=pk,
            details={
                "user_email": user.email,
                "tokens_blacklisted": tokens_blacklisted,
            }
        )
        
        return Response({
            "detail": f"All sessions terminated for {user.email}. {tokens_blacklisted} token(s) blacklisted."
        })
