"""REST API URL definitions for nautobot_topology_views."""

from nautobot.core.api.routers import OrderedDefaultRouter

from nautobot_topology_views.api import views

router = OrderedDefaultRouter()

router.register("save-coords", views.SaveCoordsViewSet)
router.register("images", views.SaveRoleImageViewSet)
router.register("xml-export", views.ExportTopoToXML)
router.register("topology-data", views.TopologyDataViewSet)
router.register("topology-mutation", views.TopologyMutationViewSet, basename="topology-mutation")

urlpatterns = router.urls
