"""
WebSocket authentication middleware for Django Channels.
Decodes JWT access token from query string (?token=<jwt>) and populates scope['user'].
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_str: str):
    """
    Validate JWT access token and return the corresponding user.
    Returns AnonymousUser if token is invalid or user not found.
    """
    try:
        access_token = AccessToken(token_str)
        user_id = access_token.get("user_id")
        if user_id is None:
            return AnonymousUser()
        return User.objects.get(pk=user_id)
    except (TokenError, User.DoesNotExist):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that authenticates WebSocket connections via JWT token
    passed in the query string: ws://host/path/?token=<jwt_access_token>
    """

    async def __call__(self, scope, receive, send):
        # Parse query string for token
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        if token_list:
            token_str = token_list[0]
            scope["user"] = await get_user_from_token(token_str)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    """
    Convenience wrapper that applies JwtAuthMiddleware to the inner application.
    """
    return JwtAuthMiddleware(inner)
