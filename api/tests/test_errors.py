"""Tests for api/exceptions.py and the permission codes."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.test import SimpleTestCase
from rest_framework import exceptions

from api import permissions
from api.exceptions import exception_handler


class ExceptionHandlerTests(SimpleTestCase):
    """Every single-message error carries a code; domain errors become 400."""

    def handle(self, exc):
        return exception_handler(exc, {})

    def test_domain_validation_error_becomes_400_with_code(self):
        response = self.handle(DjangoValidationError('Already ended.', code='membership_inactive'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'detail': 'Already ended.', 'code': 'membership_inactive'})

    def test_domain_error_without_code_gets_invalid(self):
        self.assertEqual(self.handle(DjangoValidationError('Bad.')).data['code'], 'invalid')

    def test_domain_field_errors_keep_fields_and_codes(self):
        response = self.handle(DjangoValidationError({'name': DjangoValidationError('Taken.', code='taken')}))
        self.assertEqual(response.data['name'], ['Taken.'])
        self.assertEqual(response.data['codes'], {'name': ['taken']})

    def test_drf_errors_get_their_code(self):
        cases = [
            (exceptions.NotAuthenticated(), 401, 'not_authenticated'),
            (exceptions.PermissionDenied(code='custom'), 403, 'custom'),
            (exceptions.NotFound(), 404, 'not_found'),
            (Http404(), 404, 'not_found'),
            (exceptions.Throttled(wait=5), 429, 'throttled'),
        ]
        for exc, status, code in cases:
            with self.subTest(exc=type(exc).__name__):
                response = self.handle(exc)
                self.assertEqual((response.status_code, response.data['code']), (status, code))

    def test_serializer_errors_get_a_codes_map(self):
        response = self.handle(exceptions.ValidationError({'email': ['Bad.']}, code='invalid'))
        self.assertEqual(response.data['codes'], {'email': ['invalid']})

    def test_unknown_exceptions_are_not_handled(self):
        self.assertIsNone(self.handle(ValueError()))


class PermissionCodesTests(SimpleTestCase):
    """Every custom permission has a stable code and a message."""

    def test_codes(self):
        self.assertEqual(
            {cls.__name__: cls.code for cls in (permissions.IsCenterMember, permissions.IsCenterAdmin,
                                                permissions.IsOperationalCenter)},
            {'IsCenterMember': 'not_center_member', 'IsCenterAdmin': 'not_center_admin',
             'IsOperationalCenter': 'center_not_operational'},
        )
        for cls in (permissions.IsCenterMember, permissions.IsCenterAdmin, permissions.IsOperationalCenter):
            self.assertTrue(str(cls.message))
