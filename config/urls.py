"""
Root URL configuration.

See https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # The backend has no home page: its root opens the admin (the login page when signed out)
    path('', RedirectView.as_view(url=reverse_lazy('admin:index'), permanent=False), name='home'),
    # set_language: the admin's language switcher posts here (UNFOLD["SHOW_LANGUAGES"]).
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.v1.urls')),
    # Telegram posts bot updates here in production (ADR 0023).
    path('telegram/', include('telegram_bot.urls')),
    # OpenAPI schema and Swagger UI (assets self-hosted by drf-spectacular-sidecar).
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='api-docs'),
]
