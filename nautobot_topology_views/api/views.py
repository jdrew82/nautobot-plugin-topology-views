"""REST API views for nautobot_topology_views."""

import uuid
from typing import Dict

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse, JsonResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from nautobot.circuits.models import Circuit
from nautobot.dcim.models import Cable, Device, Interface, PowerFeed, PowerPanel
from nautobot.extras.api.views import NautobotModelViewSet
from nautobot.extras.models import Role
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet, ViewSet

import nautobot_topology_views.models
from nautobot_topology_views.api.serializers import (
    RoleImageSerializer,
    TopologyDummySerializer,
)
from nautobot_topology_views.models import CoordinateGroup, RoleImage
from nautobot_topology_views.utils import (
    export_data_to_xml,
    get_image_from_url,
    topology_request_flags,
)
from nautobot_topology_views.views import (
    filtered_topology_devices_and_options,
    topology_data_from_request,
)


class SaveCoordsViewSet(PermissionRequiredMixin, ReadOnlyModelViewSet):  # pylint: disable=too-many-ancestors
    """API endpoint for saving node coordinates on the topology canvas."""

    permission_required = "nautobot_topology_views.change_coordinate"

    queryset = Device.objects.none()
    serializer_class = TopologyDummySerializer

    @action(detail=False, methods=["patch"])
    def save_coords(self, request):  # pylint: disable=too-many-branches
        """Persist x/y for a topology node (device, circuit, or power object)."""
        if not settings.PLUGINS_CONFIG["nautobot_topology_views"]["allow_coordinates_saving"]:
            return Response({"status": "not allowed to save coords"}, status=500)

        device_id = request.data.get("node_id")
        if not device_id:
            return Response({"status": "invalid node_id in body"}, status=400)

        x_coord = request.data.get("x", None)
        y_coord = request.data.get("y", None)
        group_id = request.data.get("group", "None")

        model_name = None
        actual_device = None
        if device_id.startswith("c"):
            device_id = device_id.lstrip("c")
            actual_device = Circuit.objects.get(id=device_id)
            model_name = "CircuitCoordinate"
        elif device_id.startswith("p"):
            device_id = device_id.lstrip("p")
            actual_device = PowerPanel.objects.get(id=device_id)
            model_name = "PowerPanelCoordinate"
        elif device_id.startswith("f"):
            device_id = device_id.lstrip("f")
            actual_device = PowerFeed.objects.get(id=device_id)
            model_name = "PowerFeedCoordinate"
        elif device_id.isnumeric():
            actual_device = Device.objects.get(id=device_id)
            model_name = "Coordinate"

        if not actual_device:
            return Response({"status": "invalid node_id in body"}, status=400)

        model_class = getattr(nautobot_topology_views.models, model_name)

        if group_id is None or group_id == "default":
            group_id = model_class.get_or_create_default_group(group_id)
            if not group_id:
                return Response({"status": "Error while creating default group."}, status=500)

        try:
            if CoordinateGroup.objects.filter(pk=group_id):
                group = CoordinateGroup.objects.get(pk=group_id)
                # Hen-and-egg-problem. Thanks, Django! By default, Django updates records that
                # already exist and inserts otherwise. This does not work with our
                # unique_together key if no pk is given. But: No record, no pk.
                if not model_class.objects.filter(group=group, device=actual_device):
                    # Unique group/device pair does not exist. Prepare new data set
                    coords = model_class(group=group, device=actual_device, x=x_coord, y=y_coord)
                else:
                    # Unique group/device pair already exists. Update data
                    coords = model_class(
                        pk=model_class.objects.get(group=group, device=actual_device).pk,
                        group=group,
                        device=actual_device,
                        x=x_coord,
                        y=y_coord,
                    )
                coords.save()
        except Exception:  # pylint: disable=broad-exception-caught
            return Response({"status": "Coordinates could not be saved."}, status=500)

        return Response({"status": "saved coords"})


class ExportTopoToXML(PermissionRequiredMixin, ViewSet):
    """API endpoint for exporting the topology diagram to draw.io XML format."""

    permission_required = ("dcim.view_location", "dcim.view_device")

    queryset = Device.objects.none()
    serializer_class = TopologyDummySerializer

    def list(self, request):
        """Return draw.io XML for the filtered topology when query params are present."""
        queryset, individual_options = filtered_topology_devices_and_options(request, request.user)

        params = getattr(request, "query_params", request.GET)
        if not params:
            return JsonResponse({"status": "Missing or malformed request parameters"}, status=400)

        topo_data = topology_data_from_request(request, queryset, individual_options)
        xml_data = export_data_to_xml(topo_data).decode("utf-8")

        return HttpResponse(xml_data, content_type="application/xml; charset=utf-8")


@extend_schema(exclude=True)
class TopologyDataViewSet(PermissionRequiredMixin, ViewSet):
    """API endpoint returning the same topology graph JSON as the UI (for refresh without full page load)."""

    permission_required = ("dcim.view_location", "dcim.view_device")

    queryset = Device.objects.none()
    serializer_class = TopologyDummySerializer

    def list(self, request):
        """Return nodes, edges, and coordinate group id for the current filter query string."""
        queryset, individual_options = filtered_topology_devices_and_options(request, request.user)

        params = getattr(request, "query_params", request.GET)
        if not params:
            return JsonResponse({"status": "Missing or malformed request parameters"}, status=400)

        topo_data = topology_data_from_request(request, queryset, individual_options)
        flags = topology_request_flags(request)
        if topo_data is None:
            topo_data = {"nodes": [], "edges": [], "group": flags["group_id"]}

        return Response(topo_data)


@extend_schema_view(
    quick_device=extend_schema(exclude=True),
    quick_cable=extend_schema(exclude=True),
)
class TopologyMutationViewSet(ViewSet):
    """Plugin helpers for creating devices and cables from the topology UI (validated_save, session auth)."""

    queryset = Device.objects.none()
    serializer_class = TopologyDummySerializer

    @action(detail=False, methods=["post"], url_path="quick-device")
    def quick_device(self, request):
        """Create a device with the minimum fields required for Nautobot validation."""
        if not request.user.has_perm("dcim.add_device"):
            return Response({"detail": "You do not have permission to add devices."}, status=403)

        name = request.data.get("name")
        device_type = request.data.get("device_type")
        role = request.data.get("role")
        location = request.data.get("location")
        status = request.data.get("status")
        if not name or not all((device_type, role, location, status)):
            return Response(
                {"detail": "Required: name, device_type, role, location, status (UUIDs for FKs)."},
                status=400,
            )
        try:
            device = Device(
                name=str(name).strip(),
                device_type_id=uuid.UUID(str(device_type)),
                role_id=uuid.UUID(str(role)),
                location_id=uuid.UUID(str(location)),
                status_id=uuid.UUID(str(status)),
            )
            device.validated_save()
        except (ValueError, TypeError):
            return Response({"detail": "Invalid UUID in request body."}, status=400)
        except DjangoValidationError as exc:
            return Response({"detail": getattr(exc, "message_dict", str(exc))}, status=400)

        return Response({"id": str(device.pk), "name": device.name, "display": str(device)})

    @action(detail=False, methods=["post"], url_path="quick-cable")
    def quick_cable(self, request):
        """Create a cable between two interfaces using the default Connected cable status."""
        if not request.user.has_perm("dcim.add_cable"):
            return Response({"detail": "You do not have permission to add cables."}, status=403)

        term_a = request.data.get("termination_a_id")
        term_b = request.data.get("termination_b_id")
        if not term_a or not term_b:
            return Response({"detail": "Required: termination_a_id, termination_b_id (interface UUIDs)."}, status=400)
        try:
            uuid_a = uuid.UUID(str(term_a))
            uuid_b = uuid.UUID(str(term_b))
        except (ValueError, TypeError):
            return Response({"detail": "Invalid interface UUID."}, status=400)

        if uuid_a == uuid_b:
            return Response({"detail": "A cable cannot connect an interface to itself."}, status=400)

        iface_ct = ContentType.objects.get_for_model(Interface)
        status_connected = Cable.STATUS_CONNECTED
        if status_connected is None:
            return Response(
                {"detail": "Nautobot is missing a 'Connected' status for dcim.cable; configure statuses."},
                status=500,
            )

        cable = Cable(
            termination_a_type_id=iface_ct.pk,
            termination_a_id=uuid_a,
            termination_b_type_id=iface_ct.pk,
            termination_b_id=uuid_b,
            status=status_connected,
        )
        try:
            cable.validated_save()
        except DjangoValidationError as exc:
            return Response({"detail": getattr(exc, "message_dict", str(exc))}, status=400)

        return Response({"id": str(cable.pk), "display": str(cable)})


class SaveRoleImageViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """API endpoint for saving role-to-image mappings."""

    queryset = RoleImage.objects.none()
    serializer_class = RoleImageSerializer
    permission_required = (
        "extras.add_roleimage",
        "extras.change_roleimage",
    )

    @action(detail=False, methods=["post"])
    @extend_schema(exclude=True)
    def save(self, request):
        """Bulk upsert RoleImage rows from a flat role-id / static URL map."""
        if not isinstance(request.data, dict):
            return JsonResponse({"status": "Missing or malformed request body"}, status=400)

        device_roles = {}
        for k, v in request.data.items():
            if k.isdigit() and v.startswith(settings.STATIC_URL):
                device_roles[k] = v[len(settings.STATIC_URL) :]

        content_type_ids = {}
        for k, v in request.data.items():
            if k.startswith("ct") and k[2:].isdigit() and v.startswith(settings.STATIC_URL):
                content_type_ids[k[2:]] = v[len(settings.STATIC_URL) :]

        roles: Dict[int, Role] = Role.objects.in_bulk(device_roles.keys())
        content_types: Dict[int, ContentType] = ContentType.objects.in_bulk(content_type_ids.keys())

        if len(roles) != len(device_roles):
            difference = set(device_roles) - set(roles.keys())
            return JsonResponse(
                {"status": f"Got unknown device role ids: {difference}"},
                status=400,
            )

        if len(content_types) != len(content_type_ids):
            difference = set(content_type_ids) - set(content_types.keys())
            return JsonResponse(
                {"status": f"Got unknown content type ids: {difference}"},
                status=400,
            )

        if device_roles:
            device_role_ct = ContentType.objects.get_for_model(Role)

            for role_pk, url in device_roles.items():
                RoleImage.objects.update_or_create(
                    {
                        "content_type_id": device_role_ct.pk,
                        "object_id": role_pk,
                        "image": str(get_image_from_url(url)),
                    },
                    object_id=role_pk,
                )

        for content_type_id, url in content_type_ids.items():
            RoleImage.objects.update_or_create(
                {
                    "content_type_id": content_type_id,
                    "image": str(get_image_from_url(url)),
                },
                content_type_id=content_type_id,
            )

        return JsonResponse({"status": "Ok"})
