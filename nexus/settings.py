"""
Project settings for the Nexus banking application.
Production-first security with safe local development defaults.
"""

from datetime import timedelta
from pathlib import Path
import os

# --------------------
# BASE DIR & ENV LOADING
# --------------------
BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
load_dotenv(dotenv_path=BASE_DIR / ".env")

# --------------------
# DEBUG / SECRET KEY
# --------------------
DJANGO_DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DJANGO_DEBUG:
        SECRET_KEY = "django-insecure-local-development-key"
    else:
        raise ValueError("DJANGO_SECRET_KEY environment variable is required in production")

DEBUG = DJANGO_DEBUG

IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# --------------------
# HOSTS / SECURITY
# --------------------
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "api.nexus-banking.com",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
else:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://nexus-banking.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://nexus-banking.com",
    "https://api.nexus-banking.com",
]

# --------------------
# INSTALLED APPS
# --------------------
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    "rest_framework",
    "rest_framework.authtoken",
    "djoser",

    "channels",

    "drf_spectacular",
    "django_extensions",
    "corsheaders",
    "django_filters",

    "api.apps.ApiConfig",
    "risk.apps.RiskConfig",
    "business.apps.BusinessConfig",

    "axes",
    "django_cleanup.apps.CleanupConfig",
]

SITE_ID = 1

# --------------------
# MIDDLEWARE
# --------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "risk.middleware.AuthorizationLoggingMiddleware",
    "risk.middleware.ApiKeyLoggingMiddleware",
    "risk.middleware.ErrorLoggingMiddleware",
]

# --------------------
# URLS / WSGI / ASGI
# --------------------
ROOT_URLCONF = "nexus.urls"

WSGI_APPLICATION = "nexus.wsgi.application"
ASGI_APPLICATION = "nexus.asgi.application"

# --------------------
# TEMPLATES
# --------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------
# CHANNELS
# --------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# --------------------
# DATABASE
# --------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# --------------------
# PASSWORD VALIDATION
# --------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------
# I18N
# --------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Amman"
USE_I18N = True
USE_TZ = True

# --------------------
# STATIC / MEDIA
# --------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------
# CUSTOM USER
# --------------------
AUTH_USER_MODEL = "api.User"

# --------------------
# REST / JWT
# --------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# --------------------
# ALLAUTH
# --------------------
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# --------------------
# EMAIL
# --------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --------------------
# AXES
# --------------------
AXES_FAILURE_LIMIT = 5
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 1
AXES_ENABLED = True
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
