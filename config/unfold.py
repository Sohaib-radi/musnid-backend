"""
Settings for the Unfold admin theme (``settings.UNFOLD``).

This is the only place where brand colours are defined (ADR 0008). The single
exception is the turquoise accent, which lives in
``core/static/core/css/admin.css`` because Unfold has no setting for it.

Colour scales are anchored on three brand colours and the other shades are
derived in OKLCH so that every text/background pair Unfold uses meets WCAG AA
(contrast of at least 4.5:1). ``core/tests/test_unfold.py`` measures those pairs,
so a palette change that breaks contrast fails the tests.

* ``base-900`` navy ``#12183F``: dark surfaces and important text.
* ``base-50`` blue-white ``#F2F4FF``: light surfaces.
* ``primary-600`` violet ``#6150EA``: buttons, links, active items.

Values that need a request or the URL configuration (static paths, reverses,
permission checks) are callables or lazy objects, because settings are loaded
before either exists.
"""

from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BRAND_NAVY = '#12183F'
BRAND_BLUE_WHITE = '#F2F4FF'
BRAND_VIOLET = '#6150EA'

BASE_COLORS = {
    '50': BRAND_BLUE_WHITE,
    '100': '#E4E9FB',
    '200': '#D2D8EE',
    '300': '#B7BED9',
    '400': '#8D97B8',
    '500': '#616B91',
    '600': '#4B557F',
    '700': '#353F6A',
    '800': '#212955',
    '900': BRAND_NAVY,
    '950': '#070A28',
}

PRIMARY_COLORS = {
    '50': '#F3F4FF',
    '100': '#E7E9FF',
    '200': '#D4D7FE',
    '300': '#B5BAFF',
    '400': '#9294FE',
    '500': '#766EFC',
    '600': BRAND_VIOLET,
    '700': '#4E3CC4',
    '800': '#3E309F',
    '900': '#30267D',
    '950': '#1E1657',
}


def _has_perm(permission):
    """Return a sidebar permission check for ``permission`` (``app_label.codename``)."""
    def check(request):
        return request.user.has_perm(permission)
    return check


def _nav_item(title, icon, url_name, permission, badge=None):
    item = {
        'title': title,
        'icon': icon,
        'link': reverse_lazy(url_name),
        'permission': _has_perm(permission),
    }
    if badge:
        # Dotted path to a callable(request) returning the badge text.
        item['badge'] = badge
    return item


UNFOLD = {
    # Brand name: never translated.
    'SITE_TITLE': 'Musnid',
    'SITE_HEADER': 'Musnid',
    'SITE_SYMBOL': 'menu_book',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': False,
    # Sidebar user menu offers settings.LANGUAGES (ar, en, fr) through set_language.
    'SHOW_LANGUAGES': True,
    'LOGIN': {
        'image': lambda request: static('core/img/login.svg'),
    },
    'STYLES': [
        lambda request: static('core/css/admin.css'),
    ],
    'COLORS': {
        'base': BASE_COLORS,
        'primary': PRIMARY_COLORS,
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': False,
        'navigation': [
            {
                'title': _('Centers'),
                'separator': True,
                'items': [
                    _nav_item(_('Centers'), 'apartment', 'admin:core_center_changelist', 'core.view_center',
                              badge='core.admin.pending_centers_badge'),
                    _nav_item(_('Memberships'), 'badge', 'admin:core_membership_changelist', 'core.view_membership'),
                ],
            },
            {
                'title': _('Questions and answers'),
                'separator': True,
                'items': [
                    _nav_item(_('Questions'), 'forum', 'admin:qa_question_changelist', 'qa.view_question'),
                ],
            },
            {
                'title': _('Accounts'),
                'separator': True,
                'items': [
                    _nav_item(_('Users'), 'person', 'admin:core_user_changelist', 'core.view_user'),
                    _nav_item(_('Groups'), 'group', 'admin:auth_group_changelist', 'auth.view_group'),
                ],
            },
            {
                'title': _('Knowledge base'),
                'separator': True,
                'items': [
                    _nav_item(_('Source documents'), 'menu_book', 'admin:knowledge_sourcedocument_changelist',
                              'knowledge.view_sourcedocument'),
                    _nav_item(_('Source chunks'), 'segment', 'admin:knowledge_sourcechunk_changelist',
                              'knowledge.view_sourcechunk'),
                ],
            },
            {
                'title': _('Configuration'),
                'separator': True,
                'items': [
                    _nav_item(_('API Keys'), 'vpn_key', 'admin:core_apicredential_changelist',
                              'core.view_apicredential'),
                    _nav_item(_('AI settings'), 'smart_toy', 'admin:core_aisettings_changelist',
                              'core.view_aisettings'),
                ],
            },
            {
                'title': _('Security'),
                'separator': True,
                'items': [
                    _nav_item(_('Outstanding tokens'), 'key', 'admin:token_blacklist_outstandingtoken_changelist',
                              'token_blacklist.view_outstandingtoken'),
                    _nav_item(_('Blacklisted tokens'), 'block', 'admin:token_blacklist_blacklistedtoken_changelist',
                              'token_blacklist.view_blacklistedtoken'),
                ],
            },
        ],
    },
}
