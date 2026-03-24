from nautobot.extras.plugins import TemplateExtension
from django.conf import settings
from packaging import version

NAUTOBOT_CURRENT_VERSION = version.parse(settings.VERSION)


class SiteButtons(TemplateExtension):
    model = "dcim.site"

    def buttons(self):
        return self.render("nautobot_topology_views/site_button.html")


class LocationButtons(TemplateExtension):
    model = "dcim.location"

    def buttons(self):
        return self.render("nautobot_topology_views/location_button.html")


template_extensions = [SiteButtons, LocationButtons]
