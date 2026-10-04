"""
Tests for the internationalisation settings.

Catalog completeness and translated output are covered by ``test_translations``.
"""

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import translation


class SettingsTests(SimpleTestCase):
    """Languages, middleware, catalog locations and the language switcher URL."""

    def test_languages(self):
        self.assertEqual([code for code, _name in settings.LANGUAGES], ['ar', 'en', 'fr'])
        self.assertEqual(settings.LANGUAGE_CODE, 'en')
        self.assertTrue(settings.USE_I18N)

    def test_locale_middleware_follows_sessions_and_precedes_common(self):
        middleware = settings.MIDDLEWARE
        locale = middleware.index('django.middleware.locale.LocaleMiddleware')
        self.assertGreater(locale, middleware.index('django.contrib.sessions.middleware.SessionMiddleware'))
        self.assertLess(locale, middleware.index('django.middleware.common.CommonMiddleware'))

    def test_locale_paths_put_the_project_catalog_first(self):
        self.assertEqual(
            settings.LOCALE_PATHS,
            [settings.BASE_DIR / 'locale', settings.BASE_DIR / 'locale_vendor' / 'unfold'],
        )

    def test_arabic_is_right_to_left(self):
        with translation.override('ar'):
            self.assertTrue(translation.get_language_bidi())

    def test_set_language_url(self):
        self.assertEqual(reverse('set_language'), '/i18n/setlang/')

    def test_switching_language_through_set_language(self):
        response = self.client.post('/i18n/setlang/', {'language': 'fr', 'next': '/admin/login/'})
        self.assertRedirects(response, '/admin/login/', fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'fr')
