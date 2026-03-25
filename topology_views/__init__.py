"""App declaration for topology_views."""

# Metadata is inherited from Nautobot. If not including Nautobot in the environment, this should be added
from importlib import metadata

from nautobot.apps import NautobotAppConfig

__version__ = metadata.version(__name__)


class NautobotTopologyViewsConfig(NautobotAppConfig):
    """App configuration for the topology_views app."""

    name = "topology_views"
    verbose_name = "Nautobot Topology Views"
    version = __version__
    author = "Justin Drew"
    description = "Nautobot App that draws network topology diagrams."
    base_url = "nautobot-topology-views"
    required_settings = []
    default_settings = {}
    docs_view_name = "plugins:topology_views:docs"
    searchable_models = ["roleimage"]


config = NautobotTopologyViewsConfig  # pylint:disable=invalid-name
