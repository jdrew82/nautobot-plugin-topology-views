from nautobot.extras.plugins import TemplateExtension


class SiteButtons(TemplateExtension):
    model = "dcim.site"

    def buttons(self):
        return self.render("nautobot_topology_views/site_button.html")


class LocationButtons(TemplateExtension):
    model = "dcim.location"

    def buttons(self):
        return self.render("nautobot_topology_views/location_button.html")


template_extensions = [SiteButtons, LocationButtons]
