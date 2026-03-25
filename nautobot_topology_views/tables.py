"""Table definitions for nautobot_topology_views."""

import django_tables2 as tables
from nautobot.apps.tables import BaseTable

from nautobot_topology_views.models import (
    CircuitCoordinate,
    Coordinate,
    CoordinateGroup,
    PowerFeedCoordinate,
    PowerPanelCoordinate,
)


class CoordinateGroupTable(BaseTable):
    """Table for displaying CoordinateGroup objects."""

    name = tables.Column(linkify=True)
    devices = tables.Column()

    class Meta(BaseTable.Meta):  # pylint: disable=too-few-public-methods
        """Table configuration."""

        model = CoordinateGroup
        fields = ("pk", "id", "name", "description", "devices")
        default_columns = ("name", "description", "devices")


class CircuitCoordinateTable(BaseTable):
    """Table for displaying CircuitCoordinate objects."""

    group = tables.Column(linkify=True)

    device = tables.Column(linkify=True)

    class Meta(BaseTable.Meta):  # pylint: disable=too-few-public-methods
        """Table configuration."""

        model = CircuitCoordinate
        fields = ("pk", "id", "group", "device", "x", "y")
        default_columns = ("id", "group", "device", "x", "y")


class PowerPanelCoordinateTable(BaseTable):
    """Table for displaying PowerPanelCoordinate objects."""

    group = tables.Column(linkify=True)

    device = tables.Column(linkify=True)

    class Meta(BaseTable.Meta):  # pylint: disable=too-few-public-methods
        """Table configuration."""

        model = PowerPanelCoordinate
        fields = ("pk", "id", "group", "device", "x", "y")
        default_columns = ("id", "group", "device", "x", "y")


class PowerFeedCoordinateTable(BaseTable):
    """Table for displaying PowerFeedCoordinate objects."""

    group = tables.Column(linkify=True)

    device = tables.Column(linkify=True)

    class Meta(BaseTable.Meta):  # pylint: disable=too-few-public-methods
        """Table configuration."""

        model = PowerFeedCoordinate
        fields = ("pk", "id", "group", "device", "x", "y")
        default_columns = ("id", "group", "device", "x", "y")


class CoordinateTable(BaseTable):
    """Table for displaying Coordinate objects."""

    group = tables.Column(linkify=True)

    device = tables.Column(linkify=True)

    class Meta(BaseTable.Meta):  # pylint: disable=too-few-public-methods
        """Table configuration."""

        model = Coordinate
        fields = ("pk", "id", "group", "device", "x", "y")
        default_columns = ("id", "group", "device", "x", "y")
