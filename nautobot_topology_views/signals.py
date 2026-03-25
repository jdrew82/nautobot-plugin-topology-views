"""Signal handlers for nautobot_topology_views."""

from typing import Type

from django.contrib.contenttypes.models import ContentType
from nautobot.extras.models import Role

from nautobot_topology_views.models import RoleImage


def nautobot_database_ready_callback(  # pylint: disable=unused-argument
    sender: Type[Role], *, apps, instance: Role, **kwargs
):
    """Remove RoleImage rows when a Role is deleted (content-type cleanup)."""
    ct = ContentType.objects.get_for_model(sender)
    RoleImage.objects.filter(content_type=ct, object_id=instance.id).delete()
