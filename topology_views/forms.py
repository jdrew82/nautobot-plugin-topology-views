"""Forms for topology_views."""

from django import forms
from nautobot.apps.constants import CHARFIELD_MAX_LENGTH
from nautobot.apps.forms import NautobotBulkEditForm, NautobotFilterForm, NautobotModelForm, TagsBulkEditFormMixin

from topology_views import models


class RoleImageForm(NautobotModelForm):  # pylint: disable=too-many-ancestors
    """RoleImage creation/edit form."""

    class Meta:
        """Meta attributes."""

        model = models.RoleImage
        fields = "__all__"


class RoleImageBulkEditForm(TagsBulkEditFormMixin, NautobotBulkEditForm):  # pylint: disable=too-many-ancestors
    """RoleImage bulk edit form."""

    pk = forms.ModelMultipleChoiceField(queryset=models.RoleImage.objects.all(), widget=forms.MultipleHiddenInput)
    description = forms.CharField(required=False, max_length=CHARFIELD_MAX_LENGTH)

    class Meta:
        """Meta attributes."""

        nullable_fields = [
            "description",
        ]


class RoleImageFilterForm(NautobotFilterForm):  # pylint: disable=too-many-ancestors
    """Filter form to filter searches."""

    model = models.RoleImage
    field_order = ["q", "name"]

    q = forms.CharField(
        required=False,
        label="Search",
        help_text="Search within Name.",
    )
    name = forms.CharField(required=False, label="Name")
