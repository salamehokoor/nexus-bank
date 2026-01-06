"""
Project settings for the Nexus banking application.
Security defaults favor production; local development toggles are driven by env.
"""
# nexus/settings.py
from datetime import timedelta
from pathlib import Path
import os

# Load environment variables from .env file
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
# --------------------
# BASE / DEBUG / SECRET
# --------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: Never commit real secrets! Use environment variables.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("DJANGO_DEBUG", "False").lower() == "true":
        # Only allow insecure key in DEBUG mode for local development
        SECRET_KEY = "django-insecure-development-only-key-do-not-use-in-production"
    else:
        raise ValueError("DJANGO_SECRET_KEY environment variable is required in production")

IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")

### CHANGE TO FALSE BEFORE PUSHING TO PRODUCTION
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

# --------------------
# HOSTS
# --------------------
ALLOWED_HOSTS = [
    "api.nexus-banking.com",
    "127.0.0.1",
    "localhost",
]

# Nginx passes original scheme/host to Django
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# HTTPS hardening
if DEBUG:
    # Local dev: no forced HTTPS, cookies can be sent over http
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SECURE_CONTENT_TYPE_NOSNIFF = False

    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
else:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True

# Default to HttpOnly cookies in all environments
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

CORS_ALLOWED_ORIGINS = [
    "https://nexus-banking.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "https://nexus-banking.com",
    "https://api.nexus-banking.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# --------------------
# INSTALLED APPS
# --------------------
INSTALLED_APPS = [
    # Daphne ASGI server (must be first for runserver override)
    "daphne",

    # Django core
    # 'grappelli',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Auth & accounts
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",

    # REST & auth helpers
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",  # Token revocation (Scope 1.5.7)
    "djoser",

    # Django Channels (WebSocket support)
    "channels",

    # Docs, dev, CORS
    "drf_spectacular",
    "django_extensions",
    "corsheaders",
    "django_filters",

    # Your app(s)
    "api.apps.ApiConfig",
    "risk.apps.RiskConfig",
    "axes",
    # django-cleanup MUST be last
    "django_cleanup.apps.CleanupConfig",
    "business.apps.BusinessConfig",
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
# URLS / TEMPLATES / WSGI
# --------------------
ROOT_URLCONF = "nexus.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR)],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",  # REQUIRED by allauth
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nexus.wsgi.application"
ASGI_APPLICATION = "nexus.asgi.application"

# --------------------
# CHANNEL LAYERS (WebSocket)
# --------------------
# Using InMemoryChannelLayer for local development
# For production, use Redis: channels_redis.core.RedisChannelLayer
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
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
    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]

# --------------------
# I18N
# --------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Amman"
USE_I18N = True
USE_TZ = True

# --------------------
# STATIC FILES
# --------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------
# CUSTOM USER
# --------------------
AUTH_USER_MODEL = "api.User"

# --------------------
# REST FRAMEWORK / JWT
# --------------------
REST_FRAMEWORK = {
    # JWT-only authentication for SPA + API architecture
    # SessionAuthentication is intentionally excluded to prevent CSRF enforcement
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS":
    "drf_spectacular.openapi.AutoSchema",

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    # 🔹 Global throttles
    "DEFAULT_THROTTLE_CLASSES": (
        "risk.throttling.LoggedAnonRateThrottle",
        "risk.throttling.LoggedUserRateThrottle",
        "risk.throttling.LoggedScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Global limits
        "anon": "30/minute",
        "user": "300/minute",

        # Scoped limits (used with ScopedRateThrottle + throttle_scope)
        "login": "5/minute",
        "password_reset": "3/hour",
    },
}

# Risk config
RISK_BLACKLISTED_IPS = os.environ.get(
    "RISK_BLACKLISTED_IPS",
    "").split(",") if os.environ.get("RISK_BLACKLISTED_IPS") else []
RISK_ALLOWED_API_KEYS = os.environ.get(
    "RISK_ALLOWED_API_KEYS",
    "").split(",") if os.environ.get("RISK_ALLOWED_API_KEYS") else []
CSRF_FAILURE_VIEW = "risk.views.csrf_failure_view"

SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("Bearer", ),
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    #"ROTATE_REFRESH_TOKENS": True,
    #"BLACKLIST_AFTER_ROTATION": True,
}

FRONTEND_URL = "https://nexus-banking.com"
# --------------------
# API Docs (Spectacular)
# --------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Nexus-Bank API",
    "DESCRIPTION": "Our Own Digital Bank",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Avoid schema warnings printing to stderr (was causing errors in UI load)
    "DISABLE_ERRORS_AND_WARNINGS": True,
    # Default to same-origin so Swagger "Execute" targets the server you are on
    # (local dev or prod) instead of a hard-coded host.
    "SERVERS": [{
        "url": "/"
    }],
}

# --------------------
# AI Risk Analysis (Gemini)
# --------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# drf-spectacular sometimes prints warnings during schema generation; on Windows
# writing those to stderr can raise OSError. Silence the emitter to keep
# /api/schema working even if warnings are produced.
try:
    from drf_spectacular import drainage as _drainage
    from drf_spectacular import openapi as _openapi

    # Force silent mode (mirrors DISABLE_ERRORS_AND_WARNINGS but defensive).
    _drainage.GENERATOR_STATS.silent = True

    _orig_emit = _drainage.GENERATOR_STATS.emit

    def _safe_emit(self, msg, severity):
        try:
            return _orig_emit(msg, severity)
        except OSError:
            return None

    _drainage.GeneratorStats.emit = _safe_emit
    _drainage.GENERATOR_STATS.emit = lambda *args, **kwargs: None
    _drainage.warn = lambda *args, **kwargs: None
    _drainage.error = lambda *args, **kwargs: None
    _openapi.warn = lambda *args, **kwargs: None
    _openapi.error = lambda *args, **kwargs: None
except Exception:
    pass

# --------------------
# dj-allauth
# --------------------
# dj-allauth config (email-only, NO username field)
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # custom User has no username field

# User logs in with email only
ACCOUNT_LOGIN_METHODS = {
    "email"
}  # make sure NOT {"username"} or {"email", "username"}

# Fields shown on signup form (new API: * means required)
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

# Other account rules
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"  # or "mandatory" if you want confirmation email

# Admin panel uses the default Django login URL
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/auth/social/complete/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Google OAuth — use env in prod; fallback keeps current behavior
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        'EMAIL_AUTHENTICATION': True,
        'SCOPE': ["profile", "email"],
    }
}

SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = "risk.adapters.CustomSocialAccountAdapter"

DJOSER = {
    'LOGIN_FIELD': 'email',
    'USER_CREATE_PASSWORD_RETYPE': True,
    'USERNAME_CHANGED_EMAIL_CONFIRMATION': True,
    'PASSWORD_CHANGED_EMAIL_CONFIRMATION': True,
    'SEND_CONFIRMATION_EMAIL': True,
    'SET_PASSWORD_RETYPE': True,
    'PASSWORD_RESET_CONFIRM_URL': '/password/reset/confirm/{uid}/{token}',
    'USERNAME_RESET_CONFIRM_URL': '/email/reset/confirm/{uid}/{token}',
    'ACTIVATION_URL': '/auth/activate/{uid}/{token}',
    'SEND_ACTIVATION_EMAIL': True,
    'DOMAIN': 'nexus-banking.com',
    'SITE_NAME': 'NexusBank',
    'SERIALIZERS': {
        'user_create': 'api.serializers.UserCreateSerializer',
        'user': 'api.serializers.UserSerializer',
        'user_delete': 'djoser.serializers.UserDeleteSerializer'
    },
}

# SECURITY WARNING: Use environment variables for email credentials!
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    if DEBUG:
        # Use console backend for local development if no credentials
        EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "noreply@nexus-banking.com"

AXES_FAILURE_LIMIT = 15 # lock after 5 tries
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 1  # hours before unlock
AXES_ENABLED = True
AXES_LOCKOUT_PARAMETERS = ['ip_address']

# Metrics run inline; no Celery configuration is required.