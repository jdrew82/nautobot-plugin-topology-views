"""REST API serializers for nautobot_topology_views."""

from nautobot.dcim.models import Device
from nautobot.core.api.serializers import ValidatedModelSerializer

from nautobot_topology_views.models import (
    INDIVIDUAL_OPTIONS_BOOL_DISPLAY_FIELDS,
    RoleImage,
    IndividualOptions,
    CoordinateGroup,
    Coordinate,
    CircuitCoordinate,
    PowerPanelCoordinate,
    PowerFeedCoordinate,
)


class TopologyDummySerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Minimal serializer used as a placeholder for topology API endpoints."""

    class Meta:
        model = Device
        fields = ("id", "name")


class RoleImageSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for RoleImage objects."""

    class Meta:
        model = RoleImage
        fields = ("content_type", "object_id", "image")


class CoordinateGroupSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for CoordinateGroup objects."""

    class Meta:
        model = CoordinateGroup
        fields = ("name", "description")


class CoordinateSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for Coordinate objects."""

    class Meta:
        model = Coordinate
        fields = ("x", "y")


class CircuitCoordinateSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for CircuitCoordinate objects."""

    class Meta:
        model = CircuitCoordinate
        fields = ("x", "y")


class PowerPanelCoordinateSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for PowerPanelCoordinate objects."""

    class Meta:
        model = PowerPanelCoordinate
        fields = ("x", "y")


class PowerFeedCoordinateSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for PowerFeedCoordinate objects."""

    class Meta:
        model = PowerFeedCoordinate
        fields = ("x", "y")


class IndividualOptionsSerializer(ValidatedModelSerializer):  # pylint: disable=too-many-ancestors
    """Serializer for IndividualOptions objects."""

    class Meta:
        model = IndividualOptions
        fields = ("ignore_cable_type",) + INDIVIDUAL_OPTIONS_BOOL_DISPLAY_FIELDS
