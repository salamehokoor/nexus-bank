# nexus/urls.py
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from api.views import LogoutView
from risk.views import LoggingTokenObtainPairView, LoggingTokenRefreshView

urlpatterns = [
    # Admin
    # path('grappelli/', include('grappelli.urls')),
    path('admin/', admin.site.urls),

    # Allauth UI (including Google login)
    path('accounts/', include('allauth.urls')),
    #Now allauth exposes endpoints like:
    #/accounts/login/
    #/accounts/logout/
    #/accounts/google/login/
    #/accounts/google/login/callback/

    # Djoser / JWT routes
    path("auth/jwt/create/",
         LoggingTokenObtainPairView.as_view(),
         name="jwt-create-logging"),
    path("auth/jwt/refresh/",
         LoggingTokenRefreshView.as_view(),
         name="jwt-refresh-logging"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('auth/', include('djoser.urls.jwt')),

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
