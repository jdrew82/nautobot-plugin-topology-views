"""API serializers for topology_views."""

from nautobot.apps.api import NautobotModelSerializer, TaggedModelSerializerMixin

from topology_views import models


class RoleImageSerializer(NautobotModelSerializer, TaggedModelSerializerMixin):  # pylint: disable=too-many-ancestors
    """RoleImage Serializer."""

    class Meta:
        """Meta attributes."""

        model = models.RoleImage
        fields = "__all__"

        # Option for disabling write for certain fields:
        # read_only_fields = []
