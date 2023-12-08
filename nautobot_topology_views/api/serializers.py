from nautobot.dcim.models import Device
from nautobot.core.api.serializers import ValidatedModelSerializer

from nautobot_topology_views.models import (
    RoleImage,
    IndividualOptions,
    CoordinateGroup,
    Coordinate,
    CircuitCoordinate,
    PowerPanelCoordinate,
    PowerFeedCoordinate,
)


class TopologyDummySerializer(ValidatedModelSerializer):
    class Meta:
        model = Device
        fields = ("id", "name")


class RoleImageSerializer(ValidatedModelSerializer):
    class Meta:
        model = RoleImage
        fields = ("content_type", "model_role", "image")


class CoordinateGroupSerializer(ValidatedModelSerializer):
    class Meta:
        model = CoordinateGroup
        fields = ("name", "description")


class CoordinateSerializer(ValidatedModelSerializer):
    class Meta:
        model = Coordinate
        fields = ("x", "y")


class CircuitCoordinateSerializer(ValidatedModelSerializer):
    class Meta:
        model = CircuitCoordinate
        fields = ("x", "y")


class PowerPanelCoordinateSerializer(ValidatedModelSerializer):
    class Meta:
        model = PowerPanelCoordinate
        fields = ("x", "y")


class PowerFeedCoordinateSerializer(ValidatedModelSerializer):
    class Meta:
        model = PowerFeedCoordinate
        fields = ("x", "y")


class IndividualOptionsSerializer(ValidatedModelSerializer):
    class Meta:
        model = IndividualOptions
        fields = (
            "ignore_cable_type",
            "save_coords",
            "show_unconnected",
            "show_cables",
            "show_logical_connections",
            "show_single_cable_logical_conns",
            "show_neighbors",
            "show_circuit",
            "show_power",
            "draw_default_layout",
        )
