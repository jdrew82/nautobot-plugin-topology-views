"""Plugin declaration for nautobot_topology_views."""
from importlib import metadata
from nautobot.extras.plugins import NautobotAppConfig

__version__ = metadata.version(__name__)


class NautobotTopologyViewsConfig(NautobotAppConfig):
    """Plugin configuration for the nautobot_topology_views plugin."""

    name = "nautobot_topology_views"
    verbose_name = "Nautobot Topology Views"
    description = "A Nautobot App for rendering network topologies."
    version = __version__
    author = "Justin Drew"
    author_email = "info@networktocode.com"
    base_url = "nautobot-topology-views"
    required_settings = []
    min_version = "2.0.0"
    max_version = "2.9999"
    default_settings = {
        "allow_coordinates_saving": False,
        "always_save_coordinates": False,
    }
    caching_config = {}
    searchable_models = ["coordinate", "coordinategroup"]


config = NautobotTopologyViewsConfig  # pylint:disable=invalid-name
