from typing import Type

from django.contrib.contenttypes.models import ContentType
from nautobot.extras.models import Role
from nautobot_topology_views.models import RoleImage


@receiver(pre_delete, sender=DeviceRole, dispatch_uid="delete_hanging_role_image")
def delete_hanging_role_image(sender: Type[DeviceRole], instance: DeviceRole, **kwargs):
    ct = ContentType.objects.get_for_model(sender)
    RoleImage.objects.filter(content_type=ct, object_id=instance.id).delete()
