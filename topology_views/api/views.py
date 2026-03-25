"""API views for topology_views."""

from nautobot.apps.api import NautobotModelViewSet

from topology_views import filters, models
from topology_views.api import serializers


class RoleImageViewSet(NautobotModelViewSet):  # pylint: disable=too-many-ancestors
    """RoleImage viewset."""

    queryset = models.RoleImage.objects.all()
    serializer_class = serializers.RoleImageSerializer
    filterset_class = filters.RoleImageFilterSet

    # Option for modifying the default HTTP methods:
    # http_method_names = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]
