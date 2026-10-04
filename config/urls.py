"""
Root URL configuration.

See https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # set_language: the admin's language switcher posts here (UNFOLD["SHOW_LANGUAGES"]).
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.v1.urls')),
    # OpenAPI schema and Swagger UI (assets self-hosted by drf-spectacular-sidecar).
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='api-docs'),
]
