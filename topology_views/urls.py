"""Django urlpatterns declaration for topology_views app."""

from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView
from nautobot.apps.urls import NautobotUIViewSetRouter


from topology_views import views


app_name = "topology_views"
router = NautobotUIViewSetRouter()

# The standard is for the route to be the hyphenated version of the model class name plural.
# for example, ExampleModel would be example-models.
router.register("role-images", views.RoleImageUIViewSet)


urlpatterns = [
    path("docs/", RedirectView.as_view(url=static("topology_views/docs/index.html")), name="docs"),
]

urlpatterns += router.urls
