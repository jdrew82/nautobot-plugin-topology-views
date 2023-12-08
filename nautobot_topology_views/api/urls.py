from nautobot.core.api.routers import OrderedDefaultRouter

from nautobot_topology_views.api import views

router = OrderedDefaultRouter()

# router.register("save-coords", views.SaveCoordsViewSet)
# router.register("images", views.SaveRoleImageViewSet)
# router.register("xml-export", views.ExportTopoToXML)

urlpatterns = router.urls
