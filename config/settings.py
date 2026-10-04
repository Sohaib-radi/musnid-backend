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

from pathlib import Path

from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv

from config import env
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
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Tests
# Creates the tables of test-only models (core/tests/support.py).

TEST_RUNNER = 'core.tests.runner.TestRunner'
