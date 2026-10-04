"""Tests for core/models/credentials.py: ApiCredential."""

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import ApiCredential
from core.tests.support import TEST_ENCRYPTION_KEYS, make_credential


@override_settings(FIELD_ENCRYPTION_KEYS=TEST_ENCRYPTION_KEYS)
class ApiCredentialModelTests(TestCase):
    """Masking, non-editable fields and constraints."""

    def test_masked_str_and_repr_hide_the_secret(self):
        credential = make_credential(name='Production', secret='sk-proj-0123456789abcdWXYZ')
        self.assertEqual(credential.masked, 'sk-...WXYZ')
        self.assertEqual(str(credential), 'Production (sk-...WXYZ)')
        self.assertEqual(repr(credential), '<ApiCredential openai sk-...WXYZ>')
        for text in (str(credential), repr(credential)):
            self.assertNotIn('0123456789', text)
            self.assertNotIn(credential.fingerprint, text)

    def test_only_provider_and_name_are_editable(self):
        editable = {f.name for f in ApiCredential._meta.get_fields() if getattr(f, 'editable', False)
                    and f.concrete and not f.primary_key}
        self.assertEqual(editable - {'created_by'}, {'provider', 'name'})

    def test_provider_label_is_the_brand(self):
        self.assertEqual(ApiCredential.Provider.OPENAI.label, 'OpenAI')

    def test_one_active_credential_per_provider(self):
        first = make_credential()
        duplicate = ApiCredential(provider='openai', name='x', encrypted_secret='x', fingerprint='f' * 64,
                                  prefix='sk-', last_four='abcd')
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            duplicate.save()
        self.assertIn('one_active_credential_per_provider', str(caught.exception))
        self.assertTrue(first.is_active)

    def test_active_matches_revoked_at(self):
        credential = make_credential()
        for update in ({'is_active': False}, {'revoked_at': timezone.now()}):
            with self.subTest(update=update), self.assertRaises(IntegrityError) as caught, transaction.atomic():
                ApiCredential.objects.filter(pk=credential.pk).update(**update)
            self.assertIn('credential_active_matches_revoked_at', str(caught.exception))
