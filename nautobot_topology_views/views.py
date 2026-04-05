"""Views for nautobot_topology_views."""

# Module aggregates UI, coordinate CRUD, and topology graph building.
# pylint: disable=too-many-lines

import json
import time
import uuid
from functools import reduce
from itertools import chain
from typing import DefaultDict, Dict, List, Optional, Union

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q, QuerySet
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.generic import View
from nautobot.apps.views import (
    BulkImportView,
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from nautobot.circuits.models import Circuit, CircuitTermination, ProviderNetwork
from nautobot.core.forms.forms import DynamicFilterFormSet
from nautobot.core.utils.requests import get_filterable_params_from_filter_params
from nautobot.core.views.mixins import ObjectListViewMixin
from nautobot.core.views.utils import check_filter_for_display
from nautobot.dcim.models import (
    Cable,
    Device,
    FrontPort,
    Interface,
    PowerFeed,
    PowerPanel,
    RearPort,
    device_components,
)
from nautobot.extras.models import Role

import nautobot_topology_views.models
from nautobot_topology_views.filters import (
    CircuitCoordinateFilterSet,
    CoordinateFilterSet,
    DeviceFilterSet,
    PowerFeedCoordinateFilterSet,
    PowerPanelCoordinateFilterSet,
)
from nautobot_topology_views.forms import (
    CircuitCoordinateFilterForm,
    CircuitCoordinatesForm,
    CircuitCoordinatesImportForm,
    CoordinateFilterForm,
    CoordinateGroupsForm,
    CoordinateGroupsImportForm,
    CoordinatesForm,
    CoordinatesImportForm,
    DeviceFilterForm,
    IndividualOptionsForm,
    PowerFeedCoordinateFilterForm,
    PowerFeedCoordinatesForm,
    PowerFeedCoordinatesImportForm,
    PowerPanelCoordinateFilterForm,
    PowerPanelCoordinatesForm,
    PowerPanelCoordinatesImportForm,
)
from nautobot_topology_views.models import (
    INDIVIDUAL_OPTIONS_BOOL_DISPLAY_FIELDS,
    CircuitCoordinate,
    Coordinate,
    CoordinateGroup,
    IndividualOptions,
    PowerFeedCoordinate,
    PowerPanelCoordinate,
    RoleImage,
)
from nautobot_topology_views.tables import (
    CircuitCoordinateTable,
    CoordinateGroupTable,
    CoordinateTable,
    PowerFeedCoordinateTable,
    PowerPanelCoordinateTable,
)
from nautobot_topology_views.utils import (
    CONF_IMAGE_DIR,
    IMAGE_FILETYPES,
    LinePattern,
    find_image_url,
    get_model_role,
    get_model_slug,
    image_static_url,
    is_htmx,
    topology_request_flags,
)


def get_topology_plugin_api_base_path():
    """Path segment for plugin REST API (``/api/plugins/<this>/...``). Uses app ``base_url``, not Django ``label``."""
    cfg = apps.get_app_config("nautobot_topology_views")
    slug = cfg.base_url or cfg.label
    return f"api/plugins/{slug}"


_TOPOLOGY_NON_FILTER_PARAMS = (
    frozenset(ObjectListViewMixin.non_filter_params)
    | frozenset(("draw_init", "group", "topology_include"))
    | frozenset(f for f in INDIVIDUAL_OPTIONS_BOOL_DISPLAY_FIELDS if f != "draw_default_layout")
)


def parse_topology_include_device_pks(request: HttpRequest) -> List[Union[uuid.UUID, int]]:
    """Collect device primary keys from repeated ``topology_include`` query params (UUID or int)."""
    params = getattr(request, "query_params", request.GET)
    raw = params.getlist("topology_include")
    pks: List[Union[uuid.UUID, int]] = []
    for item in raw:
        if item in (None, ""):
            continue
        s = str(item).strip()
        if not s:
            continue
        try:
            pks.append(uuid.UUID(s))
            continue
        except ValueError:
            pass
        if s.isdigit():
            pks.append(int(s))
    return pks


def get_topology_filter_display_params(request, queryset):
    """Build filter_params for Nautobot core filter_form_drawer (matches ObjectListView renderer)."""
    fs = DeviceFilterSet(request.GET, queryset)
    raw = get_filterable_params_from_filter_params(request.GET, _TOPOLOGY_NON_FILTER_PARAMS, fs)
    return [check_filter_for_display(fs.filters, name, vals) for name, vals in raw.items()]


def get_topology_dynamic_filter_form():
    """Build a DynamicFilterFormSet for the topology filter drawer."""
    return DynamicFilterFormSet(filterset=DeviceFilterSet())


def filtered_topology_devices_and_options(request, user):
    """Apply DeviceFilterSet to all devices and load or create IndividualOptions for the user."""
    params = getattr(request, "query_params", request.GET)
    base = Device.objects.all().select_related("device_type", "role")
    filtered_qs = DeviceFilterSet(params, base).qs
    include_pks = parse_topology_include_device_pks(request)
    if include_pks:
        # Do not use ``filtered_qs | extra``: FilterSet may use .distinct(); OR mixes unique/non-unique queries.
        queryset = (
            Device.objects.filter(Q(pk__in=filtered_qs) | Q(pk__in=include_pks))
            .select_related("device_type", "role")
            .distinct()
        )
    else:
        queryset = filtered_qs
    individual_options, _ = IndividualOptions.objects.get_or_create(user_id=user.id)
    return queryset, individual_options


def get_image_for_entity(entity: Union[Device, Circuit, PowerPanel, PowerFeed]):
    """Resolve topology icon URL for a device, circuit, power panel, or power feed."""
    is_device = isinstance(entity, Device)
    query = (
        {"object_id": entity.role_id}
        if is_device
        else {"content_type_id": ContentType.objects.get_for_model(entity).pk}
    )

    try:
        return RoleImage.objects.get(**query).get_image_url()
    except RoleImage.DoesNotExist:
        return find_image_url(entity.role.name if is_device else get_model_slug(entity.__class__))


def create_node(  # pylint: disable=too-many-branches,too-many-statements
    device: Union[Device, Circuit, PowerPanel, PowerFeed],
    _save_coords: bool,
    group_id="default",
):
    """Build a vis-network node dict for the given object (coordinates from DB or custom fields)."""
    node = {}
    node_content = ""
    if isinstance(device, Circuit):
        dev_name = device.cid
        node["id"] = f"c{device.pk}"
        model_name = "CircuitCoordinate"

        if device.provider is not None:
            node_content += f"<tr><th>Provider: </th><td>{device.provider.name}</td></tr>"
        if device.circuit_type is not None:
            node_content += f"<tr><th>Type: </th><td>{device.circuit_type.name}</td></tr>"
    elif isinstance(device, PowerPanel):
        dev_name = device.name
        node["id"] = f"p{device.pk}"
        model_name = "PowerPanelCoordinate"

        if device.location is not None:
            node_content += f"<tr><th>Location: </th><td>{device.location.name}</td></tr>"
    elif isinstance(device, PowerFeed):
        dev_name = device.name
        node["id"] = f"f{device.pk}"
        model_name = "PowerFeedCoordinate"

        if device.power_panel is not None:
            node_content += f"<tr><th>Power Panel: </th><td>{device.power_panel.name}</td></tr>"
        if device.type is not None:
            node_content += f"<tr><th>Type: </th><td>{device.type}</td></tr>"
        if device.supply is not None:
            node_content += f"<tr><th>Supply: </th><td>{device.supply}</td></tr>"
        if device.phase is not None:
            node_content += f"<tr><th>Phase: </th><td>{device.phase}</td></tr>"
        if device.amperage is not None:
            node_content += f"<tr><th>Amperage: </th><td>{device.amperage}</td></tr>"
        if device.voltage is not None:
            node_content += f"<tr><th>Voltage: </th><td>{device.voltage}</td></tr>"
    else:
        model_name = "Coordinate"
        dev_name = device.name
        if dev_name is None:
            dev_name = device.device_type.get_full_name

        if device.device_type is not None:
            node_content += f"<tr><th>Type: </th><td>{device.device_type.model}</td></tr>"
        if device.role.name is not None:
            node_content += f"<tr><th>Role: </th><td>{device.role.name}</td></tr>"
        if device.serial != "":
            node_content += f"<tr><th>Serial: </th><td>{device.serial}</td></tr>"
        if device.primary_ip is not None:
            node_content += f"<tr><th>IP Address: </th><td>{device.primary_ip.address}</td></tr>"
        if device.location is not None:
            node_content += f"<tr><th>Location: </th><td>{device.location.name}</td></tr>"
        if device.rack is not None:
            node_content += f"<tr><th>Rack: </th><td>{device.rack.name}</td></tr>"
        if device.position is not None:
            if device.face is not None:
                node_content += f"<tr><th>Position: </th><td>{device.position} ({device.face})</td></tr>"
            else:
                node_content += f"<tr><th>Position: </th><td>{device.position}</td></tr>"

        node["id"] = str(device.pk)

        if device.role.color != "":
            node["color.border"] = "#" + device.role.color

    model_class = getattr(nautobot_topology_views.models, model_name)

    if group_id is None or group_id == "default":
        group_id = model_class.get_or_create_default_group(group_id)
        if not group_id:
            print("Exception occured while handling default group.")
            return node

    group = get_object_or_404(CoordinateGroup, pk=group_id)

    node["physics"] = True
    # Coords must be set even if no coords have been stored. Otherwise nodes with coords
    # will not be placed correctly by vis-network.
    node["x"] = 0
    node["y"] = 0
    if model_class.objects.filter(group=group, device=device.pk).values("x") and model_class.objects.filter(
        group=group, device=device.pk
    ).values("y"):
        # Coordinates data for the device exists in Coordinates Group. Let's assign them
        node["x"] = model_class.objects.get(group=group, device=device.pk).x
        node["y"] = model_class.objects.get(group=group, device=device.pk).y
        node["physics"] = False
    elif "coordinates" in device.custom_field_data:
        # We prefer the new Coordinate model but leave the deprecated method
        # for now as fallback for compatibility reasons
        if device.custom_field_data["coordinates"] is not None:
            if ";" in device.custom_field_data["coordinates"]:
                cords = device.custom_field_data["coordinates"].split(";")
                node["x"] = int(cords[0])
                node["y"] = int(cords[1])
                node["physics"] = False

    dev_title = f"<table><tbody> {node_content}</tbody></table>"
    node["title"] = dev_title
    node["name"] = dev_name
    node["label"] = dev_name
    node["shape"] = "image"
    node["href"] = device.get_absolute_url()
    node["image"] = get_image_for_entity(device)

    return node


def create_edge(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    edge_id: int,
    termination_a: Dict,
    termination_b: Dict,
    circuit: Optional[Dict] = None,
    cable: Optional[Cable] = None,
    power: Optional[bool] = None,
    interface: Optional[Interface] = None,
):
    """Build a vis-network edge dict (cable, circuit, power, or logical interface link)."""
    cable_a_name = (
        "device A name unknown" if termination_a["termination_name"] is None else termination_a["termination_name"]
    )
    cable_a_dev_name = (
        "device A name unknown"
        if termination_a["termination_device_name"] is None
        else termination_a["termination_device_name"]
    )
    cable_b_name = (
        "device A name unknown" if termination_b["termination_name"] is None else termination_b["termination_name"]
    )
    cable_b_dev_name = (
        "cable B name unknown"
        if termination_b["termination_device_name"] is None
        else termination_b["termination_device_name"]
    )

    edge = {}
    edge["id"] = edge_id
    edge["from"] = termination_a["device_id"]
    edge["to"] = termination_b["device_id"]
    edge["color"] = "#2b7ce9"
    title = "Cable"

    if circuit is not None:
        edge["dashes"] = True
        title = f"Circuit provider: {circuit['provider_name']}<br>Termination"

    elif power is not None:
        edge["dashes"] = LinePattern.power
        title = "Power Connection"

    elif interface is not None:
        title = "Interface Connection"
        edge["width"] = 3
        edge["dashes"] = LinePattern.logical
        edge["color"] = "#f1c232"
        edge["href"] = interface.get_absolute_url() + "trace"

    edge["title"] = f"{title} between<br>{cable_a_dev_name} [{cable_a_name}]<br>{cable_b_dev_name} [{cable_b_name}]"

    if cable is not None:
        edge["href"] = cable.get_absolute_url()
        if hasattr(cable, "color") and cable.color != "":
            edge["color"] = "#" + cable.color

    return edge


def create_circuit_termination(termination):
    """Map a cable termination to vis-network termination metadata."""
    if isinstance(termination, CircuitTermination):
        return {
            "termination_name": termination.circuit.provider.name,
            "termination_device_name": termination.circuit.cid,
            "device_id": f"c{termination.circuit.pk}",
        }
    if isinstance(termination, (Interface, FrontPort, RearPort)):
        return {
            "termination_name": termination.name,
            "termination_device_name": termination.device.name,
            "device_id": str(termination.device.pk),
        }
    return None


def get_topology_data(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks
    queryset: QuerySet,
    individual_options: IndividualOptions,
    show_unconnected: bool,
    save_coords: bool,
    show_cables: bool,
    show_circuit: bool,
    show_logical_connections: bool,
    show_single_cable_logical_conns: bool,
    show_neighbors: bool,
    show_power: bool,
    group_id,
):
    """Assemble nodes and edges for the topology canvas from devices and display flags."""
    supported_termination_types = []
    for t in IndividualOptions.CHOICES:
        supported_termination_types.append(t[1])

    if not queryset:
        return None

    nodes_devices = {}
    edges = []
    nodes = []
    edge_ids = 0
    nodes_circuits: Dict[int, Circuit] = {}
    nodes_powerpanel: Dict[int, PowerPanel] = {}
    nodes_powerfeed: Dict[int, PowerFeed] = {}
    nodes_provider_networks = {}
    cable_ids = DefaultDict(dict)
    interface_ids = DefaultDict(dict)

    ignore_cable_type = individual_options.ignore_cable_type

    device_ids = [d.pk for d in queryset]
    location_ids = [d.location_id for d in queryset]

    if show_neighbors:
        interfaces = Interface.objects.filter(Q(device_id__in=device_ids))
        frontports = FrontPort.objects.filter(Q(device_id__in=device_ids))
        rearports = RearPort.objects.filter(Q(device_id__in=device_ids))

        ports = chain(interfaces, frontports, rearports)
        for port in ports:
            cable_peer = port.get_cable_peer()
            if cable_peer is not None and hasattr(cable_peer, "device") and cable_peer.device.id not in device_ids:
                device_ids.append(cable_peer.device.id)

        if show_logical_connections:
            path_complete_interfaces = Interface.objects.filter(Q(_path__is_active=True) & Q(device_id__in=device_ids))
            for path_complete_interface in path_complete_interfaces:
                connected = path_complete_interface.connected_endpoint
                if connected is not None and not isinstance(connected, ProviderNetwork):
                    device_ids.append(connected.device.id)

    if show_circuit:
        circuit_terminations = CircuitTermination.objects.filter(
            Q(location_id__in=location_ids) | Q(provider_network__isnull=False)
        ).prefetch_related("provider_network", "circuit")
        for circuit_termination in circuit_terminations:
            circuit_termination: CircuitTermination
            if show_unconnected and circuit_termination.circuit_id not in nodes_circuits:
                nodes_circuits[circuit_termination.circuit.pk] = circuit_termination.circuit

            termination_a = {}
            termination_b = {}
            circuit_model = {}
            if circuit_termination.cable is not None:
                termination_a = create_circuit_termination(circuit_termination.cable.termination_a)
                termination_b = create_circuit_termination(circuit_termination.cable.termination_b)
            elif circuit_termination.provider_network is not None:
                if circuit_termination.provider_network_id not in nodes_provider_networks:
                    nodes_provider_networks[circuit_termination.provider_network.pk] = (
                        circuit_termination.provider_network
                    )

            if bool(termination_a) and bool(termination_b):
                circuit_model = {"provider_name": circuit_termination.circuit.provider.name}
                edge_ids += 1
                edges.append(
                    create_edge(
                        edge_id=edge_ids,
                        cable=circuit_termination.cable,
                        circuit=circuit_model,
                        termination_a=termination_a,
                        termination_b=termination_b,
                    )
                )

                circuit_has_connections = False
                for termination in [
                    circuit_termination.cable.termination_a,
                    circuit_termination.cable.termination_b,
                ]:
                    if not isinstance(termination, CircuitTermination):
                        if termination.device_id not in nodes_devices and termination.device_id in device_ids:
                            nodes_devices[termination.device_id] = termination.device
                            circuit_has_connections = True
                        else:
                            if termination.device_id in device_ids:
                                circuit_has_connections = True

                if circuit_has_connections and not show_unconnected:
                    if circuit_termination.circuit_id not in nodes_circuits:
                        nodes_circuits[circuit_termination.circuit.pk] = circuit_termination.circuit

        for d in nodes_circuits.values():
            nodes.append(create_node(d, save_coords, group_id))

    if show_power:
        power_panels_ids = PowerPanel.objects.filter(Q(location_id__in=location_ids)).values_list("pk", flat=True)
        power_feeds: QuerySet[PowerFeed] = PowerFeed.objects.filter(Q(power_panel_id__in=power_panels_ids))

        for power_feed in power_feeds:
            if show_unconnected or (not show_unconnected and power_feed.cable_id is not None):
                if power_feed.power_panel_id not in nodes_powerpanel:
                    nodes_powerpanel[power_feed.power_panel.pk] = power_feed.power_panel

                power_link_name = ""
                if power_feed.pk not in nodes_powerfeed:
                    if not show_unconnected:
                        cable_peer = power_feed.get_cable_peer()
                        if cable_peer is not None and cable_peer.device_id in device_ids:
                            nodes_powerfeed[power_feed.pk] = power_feed
                            power_link_name = cable_peer.name
                    else:
                        nodes_powerfeed[power_feed.pk] = power_feed

                edge_ids += 1
                termination_a = {
                    "termination_name": power_feed.power_panel.name,
                    "termination_device_name": "",
                    "device_id": f"p{power_feed.power_panel_id}",
                }
                termination_b = {
                    "termination_name": power_feed.name,
                    "termination_device_name": power_link_name,
                    "device_id": f"f{power_feed.pk}",
                }
                edges.append(
                    create_edge(
                        edge_id=edge_ids,
                        termination_a=termination_a,
                        termination_b=termination_b,
                        power=True,
                    )
                )

                if power_feed.cable_id is not None:
                    cable_ids[power_feed.cable_id][power_feed.cable_end] = termination_b

        for d in nodes_powerfeed.values():
            nodes.append(create_node(d, save_coords, group_id))

        for d in nodes_powerpanel.values():
            nodes.append(create_node(d, save_coords, group_id))

    if show_logical_connections:
        interfaces = Interface.objects.filter(Q(_path__is_active=True) & Q(device_id__in=device_ids))

        for interface in interfaces:
            # Nautobot path API; _path is the supported way to resolve logical L2 paths
            path = interface._path  # pylint: disable=protected-access
            destination = path.destination if path else None
            if destination is not None:
                if isinstance(destination, device_components.Interface):
                    if destination.device.id not in device_ids:
                        # print('Destination interface not in device queryset, ignoring')
                        continue

                    if destination.id in interface_ids:
                        # we've already captured the destination interface, ignore this connection
                        # print('Destination interface already exists, ignoring')
                        continue

                    if (
                        not show_single_cable_logical_conns
                        and interface.cable_id == destination.cable_id
                        and show_cables
                    ):
                        # interface connection is the same as the cable connection, ignore this connection
                        continue

                    interface_ids[interface.id] = interface
                    edge_ids += 1
                    termination_a = {
                        "termination_name": interface.name,
                        "termination_device_name": interface.device.name,
                        "device_id": str(interface.device.id),
                    }
                    termination_b = {
                        "termination_name": destination.name,
                        "termination_device_name": destination.device.name,
                        "device_id": str(destination.device.id),
                    }
                    edges.append(
                        create_edge(
                            edge_id=edge_ids,
                            termination_a=termination_a,
                            termination_b=termination_b,
                            interface=interface,
                        )
                    )
                    nodes_devices[interface.device.id] = interface.device
                    nodes_devices[destination.device.id] = destination.device

    if show_cables:
        # In Nautobot 3, Cable has direct termination_a / termination_b GenericForeignKeys
        # and _termination_a_device / _termination_b_device cached ForeignKeys.
        cables = Cable.objects.filter(
            Q(_termination_a_device_id__in=device_ids) | Q(_termination_b_device_id__in=device_ids)
        )

        for cable in cables:
            term_a = cable.termination_a
            term_b = cable.termination_b
            if term_a is None or term_b is None:
                continue

            # Check if either termination type should be ignored
            term_a_type = type(term_a).__name__.lower()
            term_b_type = type(term_b).__name__.lower()
            if term_a_type in ignore_cable_type or term_b_type in ignore_cable_type:
                continue

            # Only process cables between supported termination types
            if term_a_type not in supported_termination_types or term_b_type not in supported_termination_types:
                continue

            # Skip if we've already processed this cable
            if cable.pk in cable_ids:
                continue
            cable_ids[cable.pk] = True

            # Build termination dicts
            if hasattr(term_a, "device"):
                if term_a.device_id not in nodes_devices:
                    nodes_devices[term_a.device_id] = term_a.device
                termination_a = {
                    "termination_name": term_a.name,
                    "termination_device_name": term_a.device.name,
                    "device_id": str(term_a.device_id),
                }
            else:
                continue

            if hasattr(term_b, "device"):
                if term_b.device_id not in nodes_devices:
                    nodes_devices[term_b.device_id] = term_b.device
                termination_b = {
                    "termination_name": term_b.name,
                    "termination_device_name": term_b.device.name,
                    "device_id": str(term_b.device_id),
                }
            else:
                continue

            edge_ids += 1
            edges.append(
                create_edge(
                    edge_id=edge_ids,
                    cable=cable,
                    termination_a=termination_a,
                    termination_b=termination_b,
                )
            )

    for qs_device in queryset:
        if qs_device.pk not in nodes_devices and show_unconnected:
            nodes_devices[qs_device.pk] = qs_device

    results = {}

    for d in nodes_devices.values():
        nodes.append(create_node(d, save_coords, group_id))

    results["nodes"] = nodes
    results["edges"] = edges
    results["group"] = group_id
    return results


def topology_data_from_request(request, queryset, individual_options):
    """Build topology nodes/edges from request query params and a filtered Device queryset."""
    return get_topology_data(
        queryset=queryset,
        individual_options=individual_options,
        **topology_request_flags(request),
    )


class TopologyHomeView(PermissionRequiredMixin, View):
    """Show the topology home page."""

    permission_required = ("dcim.view_location", "dcim.view_device")

    def get(  # pylint: disable=attribute-defined-outside-init,too-many-locals,too-many-branches
        self,
        request,
    ):
        """Render topology home (redirect to saved defaults, or draw canvas from GET filters)."""
        self.filterset = DeviceFilterSet
        self.queryset, individual_options = filtered_topology_devices_and_options(request, request.user)
        self.model = self.queryset.model
        topo_data = None

        if request.GET:
            if (
                "draw_init" not in request.GET
                or "draw_init" in request.GET
                and request.GET["draw_init"].lower() == "true"
            ):
                topo_data = topology_data_from_request(request, self.queryset, individual_options)

        else:
            # No GET-Request in URL. We most likely came here from the navigation menu.
            preselected_device_roles = (
                IndividualOptions.objects.get(id=individual_options.id)
                .preselected_device_roles.all()
                .values_list("id", flat=True)
            )
            preselected_tags = (
                IndividualOptions.objects.get(id=individual_options.id)
                .preselected_tags.all()
                .values_list(Lower("name"), flat=True)
            )

            q = QueryDict(mutable=True)
            q.setlist("role_id", list(preselected_device_roles))
            q.setlist("tag", list(preselected_tags))

            if individual_options.save_coords:
                q["save_coords"] = "on"
            if individual_options.show_unconnected:
                q["show_unconnected"] = "on"
            if individual_options.show_cables:
                q["show_cables"] = "on"
            if individual_options.show_logical_connections:
                q["show_logical_connections"] = "on"
            if individual_options.show_single_cable_logical_conns:
                q["show_single_cable_logical_conns"] = "on"
            if individual_options.show_neighbors:
                q["show_neighbors"] = "on"
            if individual_options.show_circuit:
                q["show_circuit"] = "on"
            if individual_options.show_power:
                q["show_power"] = "on"
            if individual_options.draw_default_layout:
                q["draw_init"] = "true"
            else:
                q["draw_init"] = "false"

            query_string = q.urlencode()
            return HttpResponseRedirect(f"{request.path}?{query_string}")

        if is_htmx(request):
            return render(
                request,
                "nautobot_topology_views/htmx_topology.html",
                {
                    "filter_form": DeviceFilterForm(request.GET, label_suffix=""),
                    "topology_data": json.dumps(topo_data),
                    "broken_image": find_image_url("role-unknown"),
                    "epoch": int(time.time()),
                    "basepath": settings.FORCE_SCRIPT_NAME or "",
                    "topology_plugin_api_base": get_topology_plugin_api_base_path(),
                },
            )

        return render(
            request,
            "nautobot_topology_views/index.html",
            {
                "filter_form": DeviceFilterForm(request.GET, label_suffix=""),
                "dynamic_filter_form": get_topology_dynamic_filter_form(),
                "filter_params": get_topology_filter_display_params(request, self.queryset),
                "topology_data": json.dumps(topo_data),
                "broken_image": find_image_url("role-unknown"),
                "model": self.model,
                "basepath": settings.FORCE_SCRIPT_NAME or "",
                "topology_plugin_api_base": get_topology_plugin_api_base_path(),
            },
        )


CONFIG = settings.PLUGINS_CONFIG["nautobot_topology_views"]
ADDITIONAL_ROLES = (PowerPanel, PowerFeed, Circuit)


class TopologyImagesView(PermissionRequiredMixin, View):
    """View for managing role-to-image mappings."""

    permission_required = (
        "dcim.view_location",
        "nautobot_topology_views.view_roleimage",
        "nautobot_topology_views.add_roleimage",
        "nautobot_topology_views.change_roleimage",
    )

    def get(self, request: HttpRequest):
        """List available icons and current RoleImage assignments for the topology UI."""
        # Scan for images in CONF_IMAGE_DIR and its img/ subdirectory
        search_dirs = [CONF_IMAGE_DIR]
        img_subdir = CONF_IMAGE_DIR / "img"
        if img_subdir.is_dir():
            search_dirs.append(img_subdir)

        images = []
        seen = set()
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            for image in search_dir.iterdir():
                if image.name.lower().endswith(IMAGE_FILETYPES) and image.stem not in seen:
                    images.append({"url": image_static_url(image), "title": image.stem})
                    seen.add(image.stem)

        roles = reduce(
            lambda acc, cur: {
                **acc,
                cur.name: {
                    "id": cur.pk,
                    "name": cur.name,
                    "image": find_image_url(cur.name),
                },
            },
            Role.objects.all(),
            {},
        )

        for additional_role in ADDITIONAL_ROLES:
            cur = get_model_role(additional_role)
            ct = ContentType.objects.get_for_model(additional_role).pk

            roles[cur.name] = {
                "id": f"ct{ct}",
                "name": cur.name,
                "image": find_image_url(cur.name),
            }

        role_images = RoleImage.objects.all()

        for role_image in role_images:
            roles[role_image.model_role.name]["image"] = role_image.get_image_url()

        return render(
            request,
            "nautobot_topology_views/images.html",
            {
                "roles": sorted(list(roles.values()), key=lambda r: r["name"]),
                "images": images,
                "basepath": settings.FORCE_SCRIPT_NAME or "",
                "topology_plugin_api_base": get_topology_plugin_api_base_path(),
            },
        )


class CircuitCoordinateView(PermissionRequiredMixin, ObjectView):
    """Detail view for a CircuitCoordinate."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = CircuitCoordinate.objects.all()


class CircuitCoordinateAddView(PermissionRequiredMixin, ObjectEditView):
    """View for creating a CircuitCoordinate."""

    permission_required = "nautobot_topology_views.add_coordinate"

    queryset = CircuitCoordinate.objects.all()
    model_form = CircuitCoordinatesForm


class CircuitCoordinateBulkImportView(BulkImportView):
    """View for bulk importing CircuitCoordinate objects."""

    queryset = CircuitCoordinate.objects.all()
    model_form = CircuitCoordinatesImportForm


class CircuitCoordinateListView(PermissionRequiredMixin, ObjectListView):
    """List view for CircuitCoordinate objects."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = CircuitCoordinate.objects.all()
    table = CircuitCoordinateTable
    filterset = CircuitCoordinateFilterSet
    filterset_form = CircuitCoordinateFilterForm


class CircuitCoordinateEditView(PermissionRequiredMixin, ObjectEditView):
    """View for editing a CircuitCoordinate."""

    permission_required = "nautobot_topology_views.change_coordinate"

    queryset = CircuitCoordinate.objects.all()
    model_form = CircuitCoordinatesForm


class CircuitCoordinateDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    """View for deleting a CircuitCoordinate."""

    permission_required = "nautobot_topology_views.delete_coordinate"

    queryset = CircuitCoordinate.objects.all()


class PowerPanelCoordinateView(PermissionRequiredMixin, ObjectView):
    """Detail view for a PowerPanelCoordinate."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = PowerPanelCoordinate.objects.all()


class PowerPanelCoordinateAddView(PermissionRequiredMixin, ObjectEditView):
    """View for creating a PowerPanelCoordinate."""

    permission_required = "nautobot_topology_views.add_coordinate"

    queryset = PowerPanelCoordinate.objects.all()
    model_form = PowerPanelCoordinatesForm


class PowerPanelCoordinateBulkImportView(BulkImportView):
    """View for bulk importing PowerPanelCoordinate objects."""

    queryset = PowerPanelCoordinate.objects.all()
    model_form = PowerPanelCoordinatesImportForm


class PowerPanelCoordinateListView(PermissionRequiredMixin, ObjectListView):
    """List view for PowerPanelCoordinate objects."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = PowerPanelCoordinate.objects.all()
    table = PowerPanelCoordinateTable
    filterset = PowerPanelCoordinateFilterSet
    filterset_form = PowerPanelCoordinateFilterForm


class PowerPanelCoordinateEditView(PermissionRequiredMixin, ObjectEditView):
    """View for editing a PowerPanelCoordinate."""

    permission_required = "nautobot_topology_views.change_coordinate"

    queryset = PowerPanelCoordinate.objects.all()
    model_form = PowerPanelCoordinatesForm


class PowerPanelCoordinateDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    """View for deleting a PowerPanelCoordinate."""

    permission_required = "nautobot_topology_views.delete_coordinate"

    queryset = PowerPanelCoordinate.objects.all()


class PowerFeedCoordinateView(PermissionRequiredMixin, ObjectView):
    """Detail view for a PowerFeedCoordinate."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = PowerFeedCoordinate.objects.all()


class PowerFeedCoordinateAddView(PermissionRequiredMixin, ObjectEditView):
    """View for creating a PowerFeedCoordinate."""

    permission_required = "nautobot_topology_views.add_coordinate"

    queryset = PowerFeedCoordinate.objects.all()
    model_form = PowerFeedCoordinatesForm


class PowerFeedCoordinateBulkImportView(BulkImportView):
    """View for bulk importing PowerFeedCoordinate objects."""

    queryset = PowerFeedCoordinate.objects.all()
    model_form = PowerFeedCoordinatesImportForm


class PowerFeedCoordinateListView(PermissionRequiredMixin, ObjectListView):
    """List view for PowerFeedCoordinate objects."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = PowerFeedCoordinate.objects.all()
    table = PowerFeedCoordinateTable
    filterset = PowerFeedCoordinateFilterSet
    filterset_form = PowerFeedCoordinateFilterForm


class PowerFeedCoordinateEditView(PermissionRequiredMixin, ObjectEditView):
    """View for editing a PowerFeedCoordinate."""

    permission_required = "nautobot_topology_views.change_coordinate"

    queryset = PowerFeedCoordinate.objects.all()
    model_form = PowerFeedCoordinatesForm


class PowerFeedCoordinateDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    """View for deleting a PowerFeedCoordinate."""

    permission_required = "nautobot_topology_views.delete_coordinate"

    queryset = PowerFeedCoordinate.objects.all()


class CoordinateView(PermissionRequiredMixin, ObjectView):
    """Detail view for a Coordinate."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = Coordinate.objects.all()


class CoordinateAddView(PermissionRequiredMixin, ObjectEditView):
    """View for creating a Coordinate."""

    permission_required = "nautobot_topology_views.add_coordinate"

    queryset = Coordinate.objects.all()
    model_form = CoordinatesForm


class CoordinateBulkImportView(BulkImportView):
    """View for bulk importing Coordinate objects."""

    queryset = Coordinate.objects.all()
    model_form = CoordinatesImportForm


class CoordinateListView(PermissionRequiredMixin, ObjectListView):
    """List view for Coordinate objects."""

    permission_required = "nautobot_topology_views.view_coordinate"

    queryset = Coordinate.objects.all()
    table = CoordinateTable
    filterset = CoordinateFilterSet
    filterset_form = CoordinateFilterForm


class CoordinateEditView(PermissionRequiredMixin, ObjectEditView):
    """View for editing a Coordinate."""

    permission_required = "nautobot_topology_views.change_coordinate"

    queryset = Coordinate.objects.all()
    model_form = CoordinatesForm


class CoordinateDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    """View for deleting a Coordinate."""

    permission_required = "nautobot_topology_views.delete_coordinate"

    queryset = Coordinate.objects.all()


class CoordinateGroupView(PermissionRequiredMixin, ObjectView):
    """Detail view for a CoordinateGroup."""

    permission_required = "nautobot_topology_views.view_coordinategroup"

    queryset = CoordinateGroup.objects.all()

    def get_extra_context(self, request, instance):
        """Attach per-type coordinate querysets for the group detail template."""
        return {
            "coordinate_tables": [
                ("Circuit Coordinates", instance.circuitcoordinate_set.all()),
                ("Power Panel Coordinates", instance.powerpanelcoordinate_set.all()),
                ("Power Feed Coordinates", instance.powerfeedcoordinate_set.all()),
                ("Device Coordinates", instance.coordinate_set.all()),
            ],
        }


class CoordinateGroupAddView(PermissionRequiredMixin, ObjectEditView):
    """View for creating a CoordinateGroup."""

    permission_required = "nautobot_topology_views.add_coordinategroup"

    queryset = CoordinateGroup.objects.all()
    model_form = CoordinateGroupsForm


class CoordinateGroupBulkImportView(BulkImportView):
    """View for bulk importing CoordinateGroup objects."""

    queryset = CoordinateGroup.objects.all()
    model_form = CoordinateGroupsImportForm


class CoordinateGroupListView(PermissionRequiredMixin, ObjectListView):
    """List view for CoordinateGroup objects."""

    permission_required = "nautobot_topology_views.view_coordinategroup"

    queryset = CoordinateGroup.objects.annotate(devices=Count("coordinate"))
    table = CoordinateGroupTable


class CoordinateGroupEditView(PermissionRequiredMixin, ObjectEditView):
    """View for editing a CoordinateGroup."""

    permission_required = "nautobot_topology_views.change_coordinategroup"

    queryset = CoordinateGroup.objects.all()
    model_form = CoordinateGroupsForm


class CoordinateGroupDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    """View for deleting a CoordinateGroup."""

    permission_required = "nautobot_topology_views.delete_coordinategroup"

    queryset = CoordinateGroup.objects.all()


class TopologyIndividualOptionsView(PermissionRequiredMixin, View):
    """View for managing per-user topology display preferences."""

    permission_required = "nautobot_topology_views.change_individualoptions"

    def post(self, request):
        """Persist topology options from POST."""
        instance = IndividualOptions.objects.get(user_id=request.user.id)
        form = IndividualOptionsForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Options have been sucessfully saved")
        else:
            messages.error(request, form.errors)

        return HttpResponseRedirect("./")

    def get(self, request):
        """Render the topology options form."""
        queryset, _ = IndividualOptions.objects.get_or_create(
            user_id=request.user.id,
        )

        form = IndividualOptionsForm(
            initial={
                "user_id": request.user.id,
                "ignore_cable_type": tuple(
                    queryset.ignore_cable_type.translate({ord(i): None for i in "[]'"}).split(", ")
                ),
                "preselected_device_roles": IndividualOptions.objects.get(
                    id=queryset.id
                ).preselected_device_roles.all(),
                "preselected_tags": IndividualOptions.objects.get(id=queryset.id).preselected_tags.all(),
                "save_coords": queryset.save_coords,
                "show_unconnected": queryset.show_unconnected,
                "show_cables": queryset.show_cables,
                "show_logical_connections": queryset.show_logical_connections,
                "show_single_cable_logical_conns": queryset.show_single_cable_logical_conns,
                "show_neighbors": queryset.show_neighbors,
                "show_circuit": queryset.show_circuit,
                "show_power": queryset.show_power,
                "draw_default_layout": queryset.draw_default_layout,
            },
        )

        return render(
            request,
            "nautobot_topology_views/individual_options.html",
            {
                "form": form,
                "object": queryset,
            },
        )
