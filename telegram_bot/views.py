"""
The webhook Telegram posts updates to in production (ADR 0023).

Telegram sends ``TELEGRAM_WEBHOOK_SECRET`` in the
``X-Telegram-Bot-Api-Secret-Token`` header (set by ``telegram_webhook --set``);
any other request gets 404, as if the URL did not exist. A handled update, even
one that failed, answers 200: otherwise Telegram resends it again and again.
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST

from telegram_bot.updates import handle_update

logger = logging.getLogger(__name__)


@csrf_exempt  # called by Telegram, authenticated by the secret header instead
@require_POST
@sensitive_variables('secret', 'sent')
def webhook(request):
    """Check the secret header, then handle the update."""
    secret = settings.TELEGRAM_WEBHOOK_SECRET
    sent = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not secret or not constant_time_compare(sent, secret):
        return HttpResponseNotFound()
    try:
        update = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()
    try:
        handle_update(update)
    except Exception:  # logged; 200 so Telegram does not resend it forever
        logger.exception('Telegram update %s failed', update.get('update_id'))
    return HttpResponse()
