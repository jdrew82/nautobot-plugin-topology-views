"""Filtering for topology_views."""

from nautobot.apps.filters import NameSearchFilterSet, NautobotFilterSet

from topology_views import models


class RoleImageFilterSet(NameSearchFilterSet, NautobotFilterSet):  # pylint: disable=too-many-ancestors
    """Filter for RoleImage."""

    class Meta:
        """Meta attributes for filter."""

        model = models.RoleImage

        # add any fields from the model that you would like to filter your searches by using those
        fields = "__all__"
