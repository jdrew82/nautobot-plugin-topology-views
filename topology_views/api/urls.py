"""Django API urlpatterns declaration for topology_views app."""

from nautobot.apps.api import OrderedDefaultRouter

from topology_views.api import views

router = OrderedDefaultRouter()
# add the name of your api endpoint, usually hyphenated model name in plural, e.g. "my-model-classes"
router.register("role-images", views.RoleImageViewSet)

app_name = "topology_views-api"
urlpatterns = router.urls
