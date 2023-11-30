from extras.plugins import PluginConfig


class TopologyViewsConfig(PluginConfig):
    name = "nautobot_topology_views"
    verbose_name = "Topology views"
    description = "An plugin to render topology maps"
    version = "3.8.1"
    author = "Mattijs Vanhaverbeke"
    author_email = "author@example.com"
    base_url = "nautobot_topology_views"
    required_settings = []
    default_settings = {
        "static_image_directory": "nautobot_topology_views/img",
        "allow_coordinates_saving": False,
        "always_save_coordinates": False,
    }

    def ready(self):
        from . import signals

        super().ready()


config = TopologyViewsConfig
