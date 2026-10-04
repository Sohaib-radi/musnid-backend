"""
Settings for the REST API: DRF, SimpleJWT and drf-spectacular.

Imported by ``config.settings``. Design: ADR 0010 (JWT), ADR 0011 (API design).
"""

from datetime import timedelta

API_PAGE_SIZE = 20

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': API_PAGE_SIZE,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Adds "code" next to "detail" and converts domain ValidationErrors (api/exceptions.py).
    'EXCEPTION_HANDLER': 'api.exceptions.exception_handler',
    # Only views that set throttle_scope are throttled (login, registration, refresh).
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'auth': '10/minute',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    # Tokens carry the public uuid, never the integer primary key.
    'USER_ID_FIELD': 'uuid',
    'USER_ID_CLAIM': 'user_uuid',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Musnid API',
    'DESCRIPTION': 'Questions about Islam answered from vetted sources, and the centers of '
                   'specialists who receive the questions the AI must not answer.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    'COMPONENT_SPLIT_REQUEST': True,
    # One schema name per choice set, whichever serializer uses it.
    'ENUM_NAME_OVERRIDES': {
        'LanguageEnum': 'core.models.choices.Language',
        'MembershipRoleEnum': 'core.models.membership.Membership.Role',
        'CenterStatusEnum': 'core.models.center.Center.Status',
    },
    # Swagger UI assets are served from drf-spectacular-sidecar, not a CDN.
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
}
