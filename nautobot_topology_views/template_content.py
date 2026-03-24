"""Template extension definitions for nautobot_topology_views."""

from nautobot.extras.plugins import TemplateExtension



class LocationButtons(TemplateExtension):
    """Add topology view button to Location detail pages."""

    model = "dcim.location"

    def detail_tabs(self):
        return []

    def full_width_page(self):
        return ""

    def left_page(self):
        return ""

    def list_buttons(self):
        return ""

    def right_page(self):
        return ""

    def buttons(self):
        return self.render("nautobot_topology_views/location_button.html")


template_extensions = [SiteButtons, LocationButtons]
