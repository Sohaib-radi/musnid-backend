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

from dotenv import load_dotenv

from config import env

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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pgvector.django',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files and uploads

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
