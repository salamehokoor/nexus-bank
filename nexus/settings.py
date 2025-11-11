from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-x@hsf*xa)67w93ndtsx$oc*&mh5xs^f)@@g5&3*1dyl2=q@g+@'
DEBUG = True

ALLOWED_HOSTS = ['13.49.41.118', 'localhost', '127.0.0.1', '13.61.99.79']
CSRF_TRUSTED_ORIGINS = ["http://13.49.41.118:8000"]

# --------------------
# INSTALLED APPS
# --------------------
INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    # REST + JWT + Docs
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'djoser',
    'django_extensions',
    'corsheaders',

    # Your app
    'api',

    # Authentication (allauth)
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

# Needed by allauth
SITE_ID = 1

# --------------------
# MIDDLEWARE
# --------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# --------------------
# URLS / TEMPLATES
# --------------------
ROOT_URLCONF = 'nexus.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',  # REQUIRED for allauth
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'nexus.wsgi.application'

# --------------------
# DATABASE
# --------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --------------------
# PASSWORD VALIDATION
# --------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator'
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator'
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator'
    },
]

# --------------------
# INTERNATIONALIZATION
# --------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --------------------
# STATIC FILES
# --------------------
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --------------------
# CUSTOM USER MODEL
# --------------------
AUTH_USER_MODEL = 'api.User'

# --------------------
# REST FRAMEWORK / JWT
# --------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS':
    'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'AUTH_HEADER_TYPES': ('JWT', ),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Nexus-Bank API',
    'DESCRIPTION': 'Our Own Digital Bank',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# --------------------
# LOGIN REDIRECTS (allauth)
# --------------------
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id':
            '33369563709-o2j5mn2ftsoscii36iqgj5ufvfkpmbge.apps.googleusercontent.com',
            'secret': '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',
            'key': ''
        }
    }
}
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # <- still needed
ACCOUNT_LOGIN_METHODS = {"email"}  # only email login
ACCOUNT_SIGNUP_FIELDS = ["email", "password1", "password2*"]  # required fields
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "optional"  # or "mandatory" if you want confirm-by-email
REST_AUTH = {"USE_JWT": True}
CORS_ALLOWED_ORIGINS = [
    "https://nexus-banking.com",
]
