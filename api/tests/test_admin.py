"""Tests for api/admin.py: token blacklist admins with Unfold."""

from django.contrib import admin
from django.test import TestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from unfold.admin import ModelAdmin

from config.unfold import UNFOLD


class TokenAdminTests(TestCase):
    """Re-registered with Unfold and listed in the "Security" sidebar group."""

    def test_registered_with_unfold(self):
        for model in (OutstandingToken, BlacklistedToken):
            with self.subTest(model=model.__name__):
                self.assertIsInstance(admin.site._registry[model], ModelAdmin)

    def test_security_sidebar_group(self):
        group = next(g for g in UNFOLD['SIDEBAR']['navigation'] if str(g['title']) == 'Security')
        self.assertEqual(
            [str(item['link']) for item in group['items']],
            ['/admin/token_blacklist/outstandingtoken/', '/admin/token_blacklist/blacklistedtoken/'],
        )
