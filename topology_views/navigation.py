"""Menu items."""

from nautobot.apps.ui import NavMenuAddButton, NavMenuGroup, NavMenuItem, NavMenuTab

items = (
    NavMenuItem(
        link="plugins:topology_views:roleimage_list",
        name="Nautobot Topology Views",
        permissions=["topology_views.view_roleimage"],
        buttons=(
            NavMenuAddButton(
                link="plugins:topology_views:roleimage_add",
                permissions=["topology_views.add_roleimage"],
            ),
        ),
    ),
)

menu_items = (
    NavMenuTab(
        name="Apps",
        groups=(NavMenuGroup(name="Nautobot Topology Views", items=tuple(items)),),
    ),
)
