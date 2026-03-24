"""Pytest configuration for nautobot_topology_views tests.

When running locally (without nautobot installed), this conftest inserts
minimal stub modules so pytest can collect test files without needing a full
Nautobot installation.  In CI, nautobot is available and these stubs are
never used.
"""
import sys
import types


def _stub_nautobot():
    """Insert lightweight stubs for nautobot modules into sys.modules."""
    if "nautobot" in sys.modules:
        return  # Real nautobot is already available; nothing to do.

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

    # Provide the minimum surface area used by nautobot_topology_views/__init__.py
    class _NautobotAppConfig:  # pylint: disable=too-few-public-methods
        """Minimal stub for NautobotAppConfig."""

    sys.modules["nautobot.extras.plugins"].NautobotAppConfig = _NautobotAppConfig


_stub_nautobot()