"""
Signals sent by ``qa`` so channels (Telegram, later others) react without ``qa``
importing them (ADR 0022).
"""

from django.dispatch import Signal

#: Sent once the transaction that opened a referral commits; argument ``referral``
referral_opened = Signal()
