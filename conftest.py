"""Root pytest configuration.

Inserts lightweight nautobot stubs into sys.modules so pytest can collect
test files without requiring a full Nautobot installation (e.g. when running
locally outside the Docker development environment).  In CI, the real nautobot
package is present and these stubs are never activated.
"""
import importlib.metadata
import sys
import types
from unittest.mock import patch


def _stub_nautobot_if_missing():
    """Insert minimal nautobot stubs when the real package is not installed."""
    if "nautobot" in sys.modules:
        return  # Real nautobot is present; nothing to do.

    stub_names = [
        "nautobot",
        "nautobot.core",
        "nautobot.core.settings",
        "nautobot.core.settings_funcs",
        "nautobot.extras",
        "nautobot.extras.plugins",
    ]
    for name in stub_names:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # Minimal stub for NautobotAppConfig, used by nautobot_topology_views/__init__.py
    class _NautobotAppConfig:  # pylint: disable=too-few-public-methods
        """Stub NautobotAppConfig."""

    sys.modules["nautobot.extras.plugins"].NautobotAppConfig = _NautobotAppConfig

    # Stub importlib.metadata.version so that nautobot_topology_views/__init__.py
    # can resolve __version__ without the package being installed.
    _real_version = importlib.metadata.version

    def _patched_version(package_name):
        if package_name == "nautobot_topology_views":
            return "0.0.0"
        return _real_version(package_name)

    importlib.metadata.version = _patched_version


_stub_nautobot_if_missing()