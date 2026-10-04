"""
Root URL configuration.

See https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # set_language: the admin's language switcher posts here (UNFOLD["SHOW_LANGUAGES"]).
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
]
