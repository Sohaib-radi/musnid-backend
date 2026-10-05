"""
Django settings for the Musnid backend.

All deployment-specific values come from environment variables, optionally
loaded from ``.env`` at the repository root. Variables already present in the
process environment take precedence over ``.env`` (python-dotenv's default),
which is how Docker Compose overrides ``POSTGRES_HOST`` and ``POSTGRES_PORT``.

The parsing rules (required vs optional, empty means unset, strict boolean)
live in ``config.env``. Every variable is documented in
``docs/getting-started/configuration.md``.

See https://docs.djangoproject.com/en/6.0/ref/settings/
"""

import os
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

from config import env
from config.api import REST_FRAMEWORK, SIMPLE_JWT, SPECTACULAR_SETTINGS  # noqa: F401
from config.unfold import UNFOLD  # noqa: F401  (read by Unfold from settings)

BASE_DIR = Path(__file__).resolve().parent.parent

# A missing file is not an error: in Docker the variables are injected by
# Compose and .env is deliberately not copied into the image.
load_dotenv(BASE_DIR / '.env')


# Core

SECRET_KEY = env.required('DJANGO_SECRET_KEY')

DEBUG = env.flag('DJANGO_DEBUG')

ALLOWED_HOSTS = env.csv_list('DJANGO_ALLOWED_HOSTS')


# Application definition

INSTALLED_APPS = [
    # Unfold must precede django.contrib.admin so its templates take priority.
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django_countries',
    'pgvector.django',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'drf_spectacular_sidecar',
    'corsheaders',
    'core',
    'knowledge',
    'qa',
    'agents',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Right after SecurityMiddleware (WhiteNoise's documented position): static files are
    # answered before sessions, locale or CSRF run (ADR 0018).
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # Before any middleware that can return a response, so error responses get CORS headers too.
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # After sessions (it may read the language from the session), before
    # CommonMiddleware (which may redirect using the active language).
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# PostgreSQL only: pgvector has no SQLite equivalent, so tests run against
# PostgreSQL too. The ENGINE uses psycopg 3 (installed as psycopg + psycopg-binary).

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env.required('POSTGRES_DB'),
        'USER': env.required('POSTGRES_USER'),
        'PASSWORD': env.required('POSTGRES_PASSWORD'),
        'HOST': env.optional('POSTGRES_HOST', 'localhost'),
        'PORT': env.optional('POSTGRES_PORT', '5435'),
    }
}


# Authentication
# Custom user identified by email (ADR 0002, ADR 0006).

AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
# LANGUAGES must match core.models.choices.Language (enforced by a test).
# Translation workflow: docs/development/translations.md

LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('ar', _('Arabic')),
    ('en', _('English')),
    ('fr', _('French')),
]

# Earlier paths win. locale_vendor/unfold holds our Arabic and French
# translations of Unfold's own strings, which Unfold does not ship.
LOCALE_PATHS = [
    BASE_DIR / 'locale',
    BASE_DIR / 'locale_vendor' / 'unfold',
]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files and uploads

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise serves the collected files from gunicorn, so the admin keeps its styles
# with DEBUG off and nginx needs no static volume (ADR 0018). Compressed (gzip) but not
# hashed: the manifest variant fails on any template whose file was not collected, which
# breaks tests and local runs that skip collectstatic.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Retrieval (docs/rag/, ADR 0015)
# A best search score below LOW_THRESHOLD means the sources do not cover the
# question. 0.30 is a starting value from 3 queries; it is calibrated with the
# 60-question evaluation planned for 2026-10-06.
LOW_THRESHOLD = 0.30
# The writer receives the evidence (summary and answer chunks) of this many
# distinct top questions; the verifier then decides full / partial / none.
EVIDENCE_QUESTIONS = 3
# Global limit of questions per UTC day, protecting the OpenAI budget (ADR 0017).
ASK_DAILY_LIMIT = env.integer('ASK_DAILY_LIMIT', 150)


# Shared cache (ADR 0017): throttle counters must be shared by every gunicorn
# worker; the default per-process memory cache would multiply each limit by the
# number of workers. Table created by `manage.py createcachetable`.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    },
}

# HTTPS behind the host nginx (ADR 0018). Off by default so local development keeps
# plain HTTP. With DJANGO_HTTPS=True Django trusts nginx's X-Forwarded-Proto: nginx
# must overwrite that header, never pass the client's. Cookies are then HTTPS-only.
HTTPS = env.flag('DJANGO_HTTPS')
if HTTPS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # nginx redirects port 80; this also covers a request that reaches gunicorn over HTTP.
    SECURE_SSL_REDIRECT = True
# 0 (default) sends no HSTS header. Raise it only once HTTPS works: browsers then refuse
# plain HTTP to this host for that many seconds, and the setting cannot be taken back early.
SECURE_HSTS_SECONDS = env.integer('DJANGO_HSTS_SECONDS', 0)

# Proxies in front of the app: DRF then takes the client IP from X-Forwarded-For.
# 0 (default) uses REMOTE_ADDR; behind one host proxy set 1. Never leave DRF's own
# default (None): it trusts the whole, client-controlled X-Forwarded-For header.
REST_FRAMEWORK['NUM_PROXIES'] = env.integer('DJANGO_NUM_PROXIES', 0)


# CrewAI (ADR 0016): no telemetry, no tracing. Set before CrewAI is imported. These
# do not stop CrewAI's first-run trace prompt; AgentsConfig.ready() declines it.
# CrewAI reads os.environ directly, so an empty value is replaced here (empty means unset).
for _name, _value in (('CREWAI_DISABLE_TELEMETRY', 'true'), ('OTEL_SDK_DISABLED', 'true'),
                      ('CREWAI_TRACING_ENABLED', 'false')):
    if not os.environ.get(_name, '').strip():
        os.environ[_name] = _value


# Secrets at rest (ADR 0014)
# Fernet keys for encrypting stored secrets such as provider API keys:
# comma-separated, newest first. The first encrypts, all decrypt (rotation).
# Deliberately separate from SECRET_KEY, so either can be rotated alone.

FIELD_ENCRYPTION_KEYS = env.csv_list('FIELD_ENCRYPTION_KEYS')

# Used only when no active OpenAI key was added in the admin.
OPENAI_API_KEY = env.optional('OPENAI_API_KEY', '')


# CORS (ADR 0012)
# Only listed origins, only on /api/, no cookies: the API authenticates with
# JWT in the Authorization header.

CORS_ALLOWED_ORIGINS = env.csv_list('DJANGO_CORS_ALLOWED_ORIGINS')
CORS_URLS_REGEX = r'^/api/.*$'
CORS_ALLOW_CREDENTIALS = False


# Tests
# Creates the tables of test-only models (core/tests/support.py).

TEST_RUNNER = 'core.tests.runner.TestRunner'
