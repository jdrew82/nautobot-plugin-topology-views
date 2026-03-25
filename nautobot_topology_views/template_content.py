"""Template extension definitions for nautobot_topology_views."""

from nautobot.extras.plugins import TemplateExtension


class LocationButtons(TemplateExtension):  # pylint: disable=abstract-method
    """Add topology view button to Location detail pages."""

    model = "dcim.location"

    def buttons(self):
        """Render topology shortcut buttons on Location detail pages."""
        return self.render("nautobot_topology_views/location_button.html")


template_extensions = [LocationButtons]
