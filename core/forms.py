"""
Admin forms for the core models.

The user forms build on Unfold's versions of Django's auth forms (styled
widgets) and rebind them to ``core.User``. Django's originals are tied to
``auth.User`` and its ``username`` field; here the identifier is ``email``,
whose uniqueness, including the case-insensitive ``unique_user_email_ci``
constraint, is checked by the model validation every ``ModelForm`` runs.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from unfold.forms import (
    AdminPasswordChangeForm as UnfoldAdminPasswordChangeForm,
    UserChangeForm as UnfoldUserChangeForm,
    UserCreationForm as UnfoldUserCreationForm,
)
from unfold.widgets import UnfoldAdminCheckboxSelectMultipleWidget, UnfoldAdminPasswordWidget

from core.models import ApiCredential, Center, Language, Membership, User
from core.services import credentials, memberships


class UserCreationForm(UnfoldUserCreationForm):
    """Create a user from an email, a full name and a password (or none)."""

    class Meta(UnfoldUserCreationForm.Meta):
        model = User
        fields = ('email', 'full_name')
        # Django's base form maps "username" to UsernameField; core.User has none.
        field_classes = {}


class UserChangeForm(UnfoldUserChangeForm):
    """Edit every field of a user; the password is shown as a read-only hash."""

    class Meta(UnfoldUserChangeForm.Meta):
        model = User
        fields = '__all__'
        field_classes = {}


class AdminPasswordChangeForm(UnfoldAdminPasswordChangeForm):
    """Set a user's password from the admin.

    Unfold's form is already model-agnostic (it receives the user instance);
    the subclass exists so the admin imports every user form from one module.
    """


class CenterAdminForm(forms.ModelForm):
    """Center form that shows the languages served as checkboxes.

    ``ArrayField`` defaults to a comma-separated text input, which invites
    typos in language codes. A multiple choice field restricted to
    ``Language`` is both clearer and validated.
    """

    languages = forms.TypedMultipleChoiceField(
        choices=Language.choices,
        required=False,
        widget=UnfoldAdminCheckboxSelectMultipleWidget,
        label=Center._meta.get_field('languages').verbose_name,
    )

    class Meta:
        model = Center
        fields = '__all__'


class MembershipAdminForm(forms.ModelForm):
    """
    Membership form that applies the membership rules as form validation.

    On creation, user, center and role are entered; on change, only the role
    (the admin makes the other fields read-only). The checks come from
    ``core.services.memberships``, so the rules are defined once; the admin
    then saves through the same services, which check again under locks.
    """

    class Meta:
        model = Membership
        fields = ['user', 'center', 'role']

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        # A ValidationError raised here becomes a form-wide error.
        if self.instance.pk:
            memberships.validate_change_role(self.instance, cleaned_data['role'])
        else:
            memberships.validate_add_member(
                cleaned_data['center'], cleaned_data['user'], cleaned_data['role'],
            )
        return cleaned_data


# Attributes that stop browsers and password managers from treating the API key
# form (a text field followed by a password field) as a login form and filling
# in the admin's own email and password. Browsers ignore autocomplete="off" on
# password fields, hence "new-password" there.
NO_AUTOFILL = {'data-1p-ignore': '', 'data-lpignore': 'true'}


class ApiCredentialAddForm(forms.ModelForm):
    """
    Add an API key. The secret is write-only: never rendered back, even after
    an invalid submission (``render_value=False``), and validated by
    ``core.services.credentials.validate_secret``.
    """

    secret = forms.CharField(
        label=_('API key'),
        strip=True,
        widget=UnfoldAdminPasswordWidget(
            attrs={'autocomplete': 'new-password', **NO_AUTOFILL}, render_value=False,
        ),
    )

    class Meta:
        model = ApiCredential
        fields = ['provider', 'name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'autocomplete': 'off', **NO_AUTOFILL})

    @method_decorator(sensitive_variables('secret'))
    def clean(self):
        cleaned_data = super().clean()
        secret = cleaned_data.get('secret')
        provider = cleaned_data.get('provider')
        if secret and provider:
            try:
                credentials.validate_secret(provider, secret)
            except ValidationError as error:
                self.add_error('secret', error)
        return cleaned_data
