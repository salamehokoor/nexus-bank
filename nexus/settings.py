# nexus/settings.py
from pathlib import Path
import os

# --------------------
# BASE / DEBUG / SECRET
# --------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Use env in prod; fall back to your current key so nothing breaks
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-x@hsf*xa)67w93ndtsx$oc*&mh5xs^f)@@g5&3*1dyl2=q@g+@")

# Keep False in production

### CHANGE TO FALSE BEFORE PUSHING TO PRODUCTION
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

# --------------------
# HOSTS
# --------------------
ALLOWED_HOSTS = [
    "api.nexus-banking.com",
    "127.0.0.1",
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

CORS_ALLOWED_ORIGINS = [
    "https://nexus-banking.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "https://nexus-banking.com",
    "https://api.nexus-banking.com",
]

# --------------------
# INSTALLED APPS
# --------------------
INSTALLED_APPS = [
    # Django core
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
    "djoser",

    # Docs, dev, CORS
    "drf_spectacular",
    "django_extensions",
    "corsheaders",

    # Your app(s)
    "api",
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
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
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
TIME_ZONE = "UTC"
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
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS":
    "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("JWT", ),
}

# --------------------
# API Docs (Spectacular)
# --------------------
SPECTACULAR_SETTINGS = {
    "TITLE":
    "Nexus-Bank API",
    "DESCRIPTION":
    "Our Own Digital Bank",
    "VERSION":
    "1.0.0",
    "SERVE_INCLUDE_SCHEMA":
    False,
    # Ensure generated server URLs are HTTPS to avoid "not secure" warnings
    "SERVERS": [{
        "url": "https://api.nexus-banking.com"
    }, {
        "url": "http://127.0.0.1:8000/"
    }],
    "logo": {
        "url": "/static/api/images/logo.png",
        "altText": "Nexus",
        "href": "/"
    },
}

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
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

AUTHENTICATION_BACKENDS = [
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

SOCIAL_ACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT: True

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
    'DOMAIN': '127.0.0.1:8000',  # default, will override below
    'SITE_NAME': 'NexusBank',
    'SERIALIZERS': {
        'user_create': 'api.serializers.UserCreateSerializer',
        'user': 'api.serializers.UserSerializer',
        'user_delete': 'djoser.serializers.UserDeleteSerializer'
    },
}

if not DEBUG:
    DJOSER['DOMAIN'] = 'api.nexus-banking.com'
    DJOSER['SITE_NAME'] = 'NexusBank'

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "nexusbank49@gmail.com"
EMAIL_HOST_PASSWORD = "olvhyvasmjcxxfat"
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
