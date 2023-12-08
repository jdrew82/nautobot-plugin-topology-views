from nautobot.core.apps import NavMenuAddButton, NavMenuImportButton, NavMenuGroup, NavMenuItem, NavMenuTab

menu_items = (
    NavMenuTab(
        name="Topology Views",
        weight=1000,
        groups=(
            NavMenuGroup(
                name="TOPOLOGY",
                weight=100,
                items=(
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:home",
                        name="Topology",
                        permissions=["dcim.view_location", "dcim.view_device"],
                    ),
                ),
            ),
            NavMenuGroup(
                name="COORDINATES",
                weight=200,
                items=(
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:coordinategroup_list",
                        name="Coordinate Groups",
                        buttons=(
                            NavMenuAddButton(
                                link="plugins:nautobot_topology_views:coordinategroup_add",
                                permissions=["nautobot_topology_views.add_coordinategroup"],
                            ),
                            NavMenuImportButton(
                                link="plugins:nautobot_topology_views:coordinategroup_import",
                                permissions=["nautobot_topology_views.add_coordinategroup"],
                            ),
                        ),
                        permissions=["nautobot_topology_views.view_coordinategroup"],
                    ),
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:coordinate_list",
                        name="Device Coordinates",
                        buttons=(
                            NavMenuAddButton(
                                link="plugins:nautobot_topology_views:coordinate_add",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                            NavMenuImportButton(
                                link="plugins:nautobot_topology_views:coordinate_import",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                        ),
                        permissions=["nautobot_topology_views.view_coordinate"],
                    ),
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:powerfeedcoordinate_list",
                        name="Power Feed Coordinates",
                        buttons=(
                            NavMenuAddButton(
                                link="plugins:nautobot_topology_views:powerfeedcoordinate_add",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                            NavMenuImportButton(
                                link="plugins:nautobot_topology_views:powerfeedcoordinate_import",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                        ),
                        permissions=["nautobot_topology_views.view_coordinate"],
                    ),
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:powerpanelcoordinate_list",
                        name="Power Panel Coordinates",
                        buttons=(
                            NavMenuAddButton(
                                link="plugins:nautobot_topology_views:powerpanelcoordinate_add",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                            NavMenuImportButton(
                                link="plugins:nautobot_topology_views:powerpanelcoordinate_import",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                        ),
                        permissions=["nautobot_topology_views.view_coordinate"],
                    ),
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:circuitcoordinate_list",
                        name="Circuit Coordinates",
                        buttons=(
                            NavMenuAddButton(
                                link="plugins:nautobot_topology_views:circuitcoordinate_add",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                            NavMenuImportButton(
                                link="plugins:nautobot_topology_views:circuitcoordinate_import",
                                permissions=["nautobot_topology_views.add_coordinate"],
                            ),
                        ),
                        permissions=["nautobot_topology_views.view_coordinate"],
                    ),
                ),
            ),
            NavMenuGroup(
                name="PREFERENCES",
                weight=300,
                items=(
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:images",
                        name="Images",
                        permissions=["dcim.view_location", "dcim.view_devicerole"],
                    ),
                    NavMenuItem(
                        link="plugins:nautobot_topology_views:individualoptions",
                        name="Individual Options",
                        permissions=["nautobot_topology_views.change_individualoptions"],
                    ),
                ),
            ),
        ),
    ),
)
