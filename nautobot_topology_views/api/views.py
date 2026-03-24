"""REST API views for nautobot_topology_views."""

from typing import Dict
import sys

from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet, ViewSet

from nautobot.circuits.models import Circuit
from nautobot.dcim.models import Device, PowerFeed, PowerPanel
from nautobot.extras.api.views import NautobotModelViewSet
from nautobot.extras.models import Role

from nautobot_topology_views.api.serializers import (
    RoleImageSerializer,
    TopologyDummySerializer,
)
import nautobot_topology_views.models
from nautobot_topology_views.models import RoleImage, CoordinateGroup
from nautobot_topology_views.views import (
    filtered_topology_devices_and_options,
    topology_data_from_request,
)
from nautobot_topology_views.utils import get_image_from_url, export_data_to_xml


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

        if sys.version_info >= (3, 9, 0):
            device_roles = {k: v.removeprefix(settings.STATIC_URL) for k, v in request.data.items() if k.isnumeric()}
            content_type_ids = {
                k[2:]: v.removeprefix(settings.STATIC_URL)
                for k, v in request.data.items()
                if k.startswith("ct") and k[2:].isnumeric()
            }
        else:
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
