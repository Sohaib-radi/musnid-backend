"""
Tests for the Unfold theme configuration (``config/unfold.py``, ADR 0008).

The contrast tests compute WCAG 2 contrast ratios for the text/background
pairs Unfold uses, so a palette change that breaks AA (4.5:1) fails here.
"""

import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import RequestFactory, SimpleTestCase, TestCase

from config.unfold import BASE_COLORS, BRAND_BLUE_WHITE, BRAND_NAVY, BRAND_VIOLET, PRIMARY_COLORS, UNFOLD
from core.tests.support import make_user

WHITE = '#FFFFFF'
ACCENT = '#2EF2C2'
AA = 4.5


def _linear(channel):
    channel /= 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    """WCAG relative luminance of ``#RRGGBB``."""
    red, green, blue = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)


def contrast(first, second):
    """WCAG contrast ratio between two ``#RRGGBB`` colours."""
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class PaletteTests(SimpleTestCase):
    """Brand anchors and WCAG AA contrast."""

    def test_brand_anchors(self):
        self.assertEqual(BASE_COLORS['900'], BRAND_NAVY)
        self.assertEqual(BASE_COLORS['50'], BRAND_BLUE_WHITE)
        self.assertEqual(PRIMARY_COLORS['600'], BRAND_VIOLET)
        self.assertIs(UNFOLD['COLORS']['base'], BASE_COLORS)
        self.assertIs(UNFOLD['COLORS']['primary'], PRIMARY_COLORS)

    def test_scales_are_complete_and_ordered_light_to_dark(self):
        steps = ['50', '100', '200', '300', '400', '500', '600', '700', '800', '900', '950']
        for name, scale in (('base', BASE_COLORS), ('primary', PRIMARY_COLORS)):
            with self.subTest(scale=name):
                self.assertEqual(list(scale), steps)
                values = [luminance(scale[step]) for step in steps]
                self.assertEqual(values, sorted(values, reverse=True))

    def test_text_pairs_meet_wcag_aa(self):
        # Unfold's font colours: subtle = base-500/400, default = base-600/300,
        # important = base-900/100 (light/dark). Primary is used for buttons
        # (white text) and links.
        pairs = {
            'subtle text on white': (BASE_COLORS['500'], WHITE),
            'subtle text on base-50': (BASE_COLORS['500'], BASE_COLORS['50']),
            'default text on white': (BASE_COLORS['600'], WHITE),
            'important text on white': (BASE_COLORS['900'], WHITE),
            'subtle text on dark base-900': (BASE_COLORS['400'], BASE_COLORS['900']),
            'subtle text on dark base-950': (BASE_COLORS['400'], BASE_COLORS['950']),
            'default text on dark base-900': (BASE_COLORS['300'], BASE_COLORS['900']),
            'important text on dark base-900': (BASE_COLORS['100'], BASE_COLORS['900']),
            'button text on primary-600': (WHITE, PRIMARY_COLORS['600']),
            'link primary-600 on white': (PRIMARY_COLORS['600'], WHITE),
            'link primary-600 on base-50': (PRIMARY_COLORS['600'], BASE_COLORS['50']),
            'dark-mode link primary-400 on base-900': (PRIMARY_COLORS['400'], BASE_COLORS['900']),
            'accent on navy': (ACCENT, BRAND_NAVY),
        }
        for name, (text, background) in pairs.items():
            with self.subTest(pair=name):
                self.assertGreaterEqual(contrast(text, background), AA)

    def test_admin_css_defines_no_colour_but_the_accent(self):
        css = open(finders.find('core/css/admin.css'), encoding='utf-8').read()
        self.assertEqual(set(re.findall(r'#[0-9A-Fa-f]{6}\b', css)), {ACCENT})


class AssetsTests(SimpleTestCase):
    """Typeface, licence and login artwork are present and wired in."""

    def test_font_files_and_licence(self):
        for name in ('readex-pro-arabic.woff2', 'readex-pro-latin.woff2', 'readex-pro-latin-ext.woff2'):
            with self.subTest(font=name):
                self.assertIsNotNone(finders.find(f'core/fonts/readex-pro/{name}'))
        licence = open(finders.find('core/fonts/readex-pro/OFL.txt'), encoding='utf-8').read()
        self.assertIn('SIL Open Font License, Version 1.1', licence)

    def test_admin_css_uses_readex_pro(self):
        css = open(finders.find('core/css/admin.css'), encoding='utf-8').read()
        self.assertIn('--font-sans: "Readex Pro"', css)
        self.assertEqual(css.count('@font-face'), 3)

    def test_login_image_and_styles_resolve_to_static_files(self):
        request = RequestFactory().get('/')
        self.assertEqual(UNFOLD['LOGIN']['image'](request), '/static/core/img/login.svg')
        self.assertEqual([style(request) for style in UNFOLD['STYLES']], ['/static/core/css/admin.css'])
        self.assertIsNotNone(finders.find('core/img/login.svg'))


class SettingsTests(SimpleTestCase):
    """App order, site identity and language switcher."""

    def test_unfold_precedes_django_admin(self):
        apps = settings.INSTALLED_APPS
        self.assertLess(apps.index('unfold'), apps.index('django.contrib.admin'))

    def test_site_identity_is_the_untranslated_brand(self):
        self.assertEqual(UNFOLD['SITE_TITLE'], 'Musnid')
        self.assertEqual(UNFOLD['SITE_HEADER'], 'Musnid')

    def test_language_switcher_is_enabled(self):
        self.assertTrue(UNFOLD['SHOW_LANGUAGES'])


class SidebarTests(TestCase):
    """Sidebar groups, icons, links and permission checks."""

    def test_groups_and_items(self):
        layout = [
            ([str(item['title']) for item in group['items']], str(group['title']))
            for group in UNFOLD['SIDEBAR']['navigation']
        ]
        self.assertEqual(layout, [(['Centers', 'Memberships'], 'Centers'), (['Users', 'Groups'], 'Accounts')])

    def test_every_item_has_icon_link_and_permission(self):
        links = {
            '/admin/core/center/', '/admin/core/membership/', '/admin/core/user/', '/admin/auth/group/',
        }
        seen = set()
        for group in UNFOLD['SIDEBAR']['navigation']:
            for item in group['items']:
                with self.subTest(item=str(item['title'])):
                    self.assertTrue(item['icon'])
                    self.assertTrue(callable(item['permission']))
                    seen.add(str(item['link']))
        self.assertEqual(seen, links)

    def test_permission_checks_follow_model_permissions(self):
        request = RequestFactory().get('/admin/')
        items = [item for group in UNFOLD['SIDEBAR']['navigation'] for item in group['items']]
        request.user = make_user(is_staff=True)
        self.assertEqual([item['permission'](request) for item in items], [False] * 4)
        request.user = make_user(is_staff=True, is_superuser=True)
        self.assertEqual([item['permission'](request) for item in items], [True] * 4)
