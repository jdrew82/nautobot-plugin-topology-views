"""Filter definitions for nautobot_topology_views."""

import django_filters
from django.db.models import Q
from nautobot.circuits.models import Circuit
from nautobot.core.filters import (
    MultiValueCharFilter,
    MultiValueMACAddressFilter,
    SearchFilter,
    TreeNodeMultipleChoiceFilter,
)
from nautobot.dcim.choices import DeviceStatusChoices
from nautobot.dcim.models import (
    Device,
    DeviceType,
    Location,
    Manufacturer,
    Platform,
    PowerFeed,
    PowerPanel,
    Rack,
)
from nautobot.extras.filters import NautobotFilterSet
from nautobot.extras.models import Role
from nautobot.tenancy.filter_mixins import TenancyModelFilterSetMixin

from nautobot_topology_views.models import (
    CircuitCoordinate,
    Coordinate,
    CoordinateGroup,
    PowerFeedCoordinate,
    PowerPanelCoordinate,
)


class DeviceFilterSet(NautobotFilterSet, TenancyModelFilterSetMixin):  # pylint: disable=too-many-ancestors
    """FilterSet for Device objects used in the topology view."""

    q = SearchFilter(filter_predicates={"name": "icontains"})
    manufacturer = django_filters.ModelMultipleChoiceFilter(
        field_name="device_type__manufacturer",
        queryset=Manufacturer.objects.all(),
        to_field_name="name",
        label="Manufacturer",
    )
    device_type = django_filters.ModelMultipleChoiceFilter(
        queryset=DeviceType.objects.all(),
        to_field_name="name",
        label="DeviceType",
    )
    role_id = django_filters.ModelMultipleChoiceFilter(
        field_name="role_id",
        queryset=Role.objects.all(),
        label="Role (ID)",
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Platform.objects.all(),
        label="Platform (ID)",
    )
    location_id = TreeNodeMultipleChoiceFilter(
        queryset=Location.objects.all(),
        field_name="location",
        lookup_expr="in",
        label="Location",
    )
    rack_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Rack.objects.all(),
        field_name="rack_id",
        label="Rack (ID)",
    )
    status = django_filters.MultipleChoiceFilter(
        choices=DeviceStatusChoices,
        null_value=None,
    )
    mac_address = MultiValueMACAddressFilter(
        field_name="interfaces__mac_address",
        label="MAC address",
    )
    serial = MultiValueCharFilter(lookup_expr="iexact")
    console_ports = django_filters.BooleanFilter(
        method="_console_ports",
        label="Has console ports",
    )
    console_server_ports = django_filters.BooleanFilter(
        method="_console_server_ports",
        label="Has console server ports",
    )
    power_ports = django_filters.BooleanFilter(
        method="_power_ports",
        label="Has power ports",
    )
    power_outlets = django_filters.BooleanFilter(
        method="_power_outlets",
        label="Has power outlets",
    )
    interfaces = django_filters.BooleanFilter(
        method="_interfaces",
        label="Has interfaces",
    )
    pass_through_ports = django_filters.BooleanFilter(
        method="_pass_through_ports",
        label="Has pass-through ports",
    )
    has_primary_ip = django_filters.BooleanFilter(
        method="_has_primary_ip",
        label="Has a primary IP",
    )
    has_oob_ip = django_filters.BooleanFilter(
        method="_has_oob_ip",
        label="Has an out-of-band IP",
    )
    virtual_chassis_member = django_filters.BooleanFilter(
        method="_virtual_chassis_member",
        label="Is a virtual chassis member",
    )

    class Meta:
        """FilterSet configuration."""

        model = Device
        fields = "__all__"

    def _console_ports(self, queryset, _name, value):
        return queryset.exclude(consoleports__isnull=value)

    def _console_server_ports(self, queryset, _name, value):
        return queryset.exclude(consoleserverports__isnull=value)

    def _power_ports(self, queryset, _name, value):
        return queryset.exclude(powerports__isnull=value)

    def _power_outlets(self, queryset, _name, value):
        return queryset.exclude(poweroutlets__isnull=value)

    def _interfaces(self, queryset, _name, value):
        return queryset.exclude(interfaces__isnull=value)

    def _pass_through_ports(self, queryset, _name, value):
        return queryset.exclude(frontports__isnull=value, rearports__isnull=value)

    def _has_primary_ip(self, queryset, _name, value):
        params = Q(primary_ip4__isnull=False) | Q(primary_ip6__isnull=False)
        if value:
            return queryset.filter(params)
        return queryset.exclude(params)

    def _has_oob_ip(self, queryset, _name, value):
        params = Q(oob_ip__isnull=False)
        if value:
            return queryset.filter(params)
        return queryset.exclude(params)

    def _virtual_chassis_member(self, queryset, _name, value):
        return queryset.exclude(virtual_chassis__isnull=value)


class CircuitCoordinateFilterSet(NautobotFilterSet):
    """FilterSet for CircuitCoordinate objects."""

    q = SearchFilter(
        filter_predicates={
            "group__name": "icontains",
            "device__name": "icontains",
        }
    )
    group = django_filters.ModelMultipleChoiceFilter(
        queryset=CoordinateGroup.objects.all(),
    )

    device = django_filters.ModelMultipleChoiceFilter(
        queryset=Circuit.objects.all(),
    )

    class Meta:
        """FilterSet configuration."""

        model = CircuitCoordinate
        fields = "__all__"


class PowerPanelCoordinateFilterSet(NautobotFilterSet):
    """FilterSet for PowerPanelCoordinate objects."""

    q = SearchFilter(
        filter_predicates={
            "group__name": "icontains",
            "device__name": "icontains",
        }
    )
    group = django_filters.ModelMultipleChoiceFilter(
        queryset=CoordinateGroup.objects.all(),
    )

    device = django_filters.ModelMultipleChoiceFilter(
        queryset=PowerPanel.objects.all(),
    )

    class Meta:
        """FilterSet configuration."""

        model = PowerPanelCoordinate
        fields = "__all__"


class PowerFeedCoordinateFilterSet(NautobotFilterSet):
    """FilterSet for PowerFeedCoordinate objects."""

    q = SearchFilter(
        filter_predicates={
            "group__name": "icontains",
            "device__name": "icontains",
        }
    )
    group = django_filters.ModelMultipleChoiceFilter(
        queryset=CoordinateGroup.objects.all(),
    )

    device = django_filters.ModelMultipleChoiceFilter(
        queryset=PowerFeed.objects.all(),
    )

    class Meta:
        """FilterSet configuration."""

        model = PowerFeedCoordinate
        fields = "__all__"


class CoordinateFilterSet(NautobotFilterSet):
    """FilterSet for Coordinate objects."""

    q = SearchFilter(
        filter_predicates={
            "group__name": "icontains",
            "device__name": "icontains",
        }
    )
    group = django_filters.ModelMultipleChoiceFilter(
        queryset=CoordinateGroup.objects.all(),
    )

    device = django_filters.ModelMultipleChoiceFilter(
        queryset=Device.objects.all(),
    )

    class Meta:
        """FilterSet configuration."""

        model = Coordinate
        fields = "__all__"
