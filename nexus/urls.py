"""
Root URL configuration for the Nexus project.
Includes admin, auth, API docs, risk, business, and core API routes.

AUTHENTICATION FLOW:
- 2FA Login: POST /auth/login/init/ → POST /auth/login/verify/
- Token Refresh: POST /auth/jwt/refresh/
- Social Login: /accounts/google/login/
"""
# nexus/urls.py
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from api.views import LogoutView
from risk.views import LoggingTokenRefreshView

urlpatterns = [
    # Admin
    # path('grappelli/', include('grappelli.urls')),
    path('admin/', admin.site.urls),

    # Allauth UI (including Google login)
    path('accounts/', include('allauth.urls')),
    # Allauth exposes endpoints like:
    # /accounts/login/
    # /accounts/logout/
    # /accounts/google/login/
    # /accounts/google/login/callback/

    # ==========================================================================
    # JWT Token Management (2FA login endpoints are in api/urls.py)
    # ==========================================================================
    # REMOVED: LoggingTokenObtainPairView - use 2FA flow via /auth/login/init/ + /auth/login/verify/
    # REMOVED: djoser.urls.jwt - exposes TokenObtainPairView which bypasses 2FA
    # REMOVED: djoser.urls.authtoken - exposes /auth/token/login/ which bypasses 2FA
    
    # Token refresh - extends session without re-authentication
    path("auth/token/refresh/",
         LoggingTokenRefreshView.as_view(),
         name="token-refresh"),
    
    # Logout - marks user offline
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    
    # Djoser routes for registration and password management ONLY (no login)
    path('auth/', include('djoser.urls')),

    # ✅ API schema and docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/',
         SpectacularSwaggerView.as_view(url_name='schema'),
         name='swagger-ui'),
    path('api/schema/redoc/',
         SpectacularRedocView.as_view(url_name='schema'),
         name='redoc'),

    ## Risk module
    path("risk/", include("risk.urls")),
    ## business module
    path("business/", include("business.urls")),

    ###
    path('', include('api.urls')),
]

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns += [
    path("auth/jwt/create/", TokenObtainPairView.as_view(), name="jwt-create"),
    path("auth/jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
]
