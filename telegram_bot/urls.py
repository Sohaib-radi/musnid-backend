"""URL of the Telegram webhook (ADR 0023), included under ``telegram/``."""

from django.urls import path

from telegram_bot import views

app_name = 'telegram_bot'

urlpatterns = [
    path('webhook/', views.webhook, name='webhook'),
]
