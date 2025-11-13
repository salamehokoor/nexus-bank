# nexus/urls.py
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Allauth UI (including Google login)
    path('accounts/', include('allauth.urls')),
    #Now allauth exposes endpoints like:
    #/accounts/login/
    #/accounts/logout/
    #/accounts/google/login/
    #/accounts/google/login/callback/

    # Djoser / JWT routes
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
    ###
    path('', include('api.urls')),
]
