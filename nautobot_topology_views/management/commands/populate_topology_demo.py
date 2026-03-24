"""Management command to populate Nautobot with demo data for Topology Views."""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from nautobot.circuits.models import Circuit, CircuitTermination, CircuitType, Provider
from nautobot.dcim.choices import InterfaceTypeChoices
from nautobot.dcim.models import (
    Cable,
    Device,
    DeviceType,
    Interface,
    InterfaceTemplate,
    Location,
    LocationType,
    Manufacturer,
    Rack,
)
from nautobot.extras.models import Role, Status, Tag
from nautobot.ipam.models import IPAddress, IPAddressToInterface, Namespace, Prefix

DEMO_TAG_NAME = "topology-demo"

# --- Site definitions ---
SITES = [
    {"name": "NYC-DC1", "description": "New York Data Center 1"},
    {"name": "LAX-DC1", "description": "Los Angeles Data Center 1"},
]

# --- Manufacturer & DeviceType definitions ---
DEVICE_TYPES = [
    {
        "manufacturer": "Cisco",
        "model": "Nexus 9504",
        "u_height": 7,
        "interfaces": [
            ("Ethernet1/{}", InterfaceTypeChoices.TYPE_100GE_QSFP28, 8),
        ],
    },
    {
        "manufacturer": "Arista",
        "model": "7050X",
        "u_height": 1,
        "interfaces": [
            ("Ethernet{}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS, 48),
            ("Ethernet{}", InterfaceTypeChoices.TYPE_40GE_QSFP_PLUS, 4, 49),  # start numbering at 49
        ],
    },
    {
        "manufacturer": "Cisco",
        "model": "ASR 9001",
        "u_height": 2,
        "interfaces": [
            ("TenGigE0/0/0/{}", InterfaceTypeChoices.TYPE_10GE_SFP_PLUS, 8),
        ],
    },
]

# --- Role definitions ---
ROLES = [
    {"name": "Spine", "color": "2196F3", "description": "Spine / Core switch"},
    {"name": "Leaf", "color": "4CAF50", "description": "Leaf / Access switch"},
    {"name": "Border Router", "color": "FF9800", "description": "WAN / Edge router"},
]

# --- Per-site device inventory ---
SITE_DEVICES = [
    # (name template, role, device_type model, count)
    ("{site}-spine-{i}", "Spine", "Nexus 9504", 2),
    ("{site}-leaf-{i}", "Leaf", "7050X", 4),
    ("{site}-border-{i}", "Border Router", "ASR 9001", 2),
]

# --- Management network per site (index matches SITES order) ---
MGMT_PREFIXES = ["10.1.0.0/24", "10.2.0.0/24"]


def _get_or_create_status(name, model_class, color="4caf50"):
    """Get or create a Status and ensure it is associated with the given model."""
    status, _ = Status.objects.get_or_create(name=name, defaults={"color": color})
    ct = ContentType.objects.get_for_model(model_class)
    if not status.content_types.filter(pk=ct.pk).exists():
        status.content_types.add(ct)
    return status


def _get_or_create_role(name, model_class, color="9e9e9e", description=""):
    """Get or create a Role and ensure it is associated with the given model."""
    role, _ = Role.objects.get_or_create(name=name, defaults={"color": color, "description": description})
    ct = ContentType.objects.get_for_model(model_class)
    if not role.content_types.filter(pk=ct.pk).exists():
        role.content_types.add(ct)
    return role


class Command(BaseCommand):
    help = "Populate Nautobot with demo network topology data for the Topology Views app."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Remove all demo objects (identified by the 'topology-demo' tag).",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()
            return
        self._populate()

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def _flush(self):
        tag = Tag.objects.filter(name=DEMO_TAG_NAME).first()
        if not tag:
            self.stdout.write(self.style.WARNING("No demo tag found — nothing to flush."))
            return

        models_to_flush = [
            IPAddressToInterface,
            IPAddress,
            Prefix,
            Cable,
            CircuitTermination,
            Circuit,
            Device,
            Rack,
            Location,
        ]

        with transaction.atomic():
            # Delete cables first (they reference interfaces which reference devices)
            cables = Cable.objects.filter(tags=tag)
            count = cables.count()
            cables.delete()
            self.stdout.write(f"  Deleted {count} cables")

            # Delete circuit terminations + circuits
            circuits = Circuit.objects.filter(tags=tag)
            CircuitTermination.objects.filter(circuit__in=circuits).delete()
            count = circuits.count()
            circuits.delete()
            self.stdout.write(f"  Deleted {count} circuits")

            # Delete IP assignments, IPs, prefixes
            ips = IPAddress.objects.filter(tags=tag)
            IPAddressToInterface.objects.filter(ip_address__in=ips).delete()
            count = ips.count()
            ips.delete()
            self.stdout.write(f"  Deleted {count} IP addresses")

            prefixes = Prefix.objects.filter(tags=tag)
            count = prefixes.count()
            prefixes.delete()
            self.stdout.write(f"  Deleted {count} prefixes")

            # Delete devices (interfaces cascade)
            devices = Device.objects.filter(tags=tag)
            count = devices.count()
            devices.delete()
            self.stdout.write(f"  Deleted {count} devices")

            # Delete racks
            racks = Rack.objects.filter(tags=tag)
            count = racks.count()
            racks.delete()
            self.stdout.write(f"  Deleted {count} racks")

            # Delete locations
            locations = Location.objects.filter(tags=tag)
            count = locations.count()
            locations.delete()
            self.stdout.write(f"  Deleted {count} locations")

        self.stdout.write(self.style.SUCCESS("Flush complete."))

    # ------------------------------------------------------------------
    # Populate
    # ------------------------------------------------------------------

    @transaction.atomic
    def _populate(self):
        self.stdout.write("Creating demo topology data...")

        # -- Tag --
        demo_tag, _ = Tag.objects.get_or_create(name=DEMO_TAG_NAME, defaults={"description": "Auto-generated demo data for Topology Views"})
        # Ensure tag applies to all the content types we need
        for model_cls in (Device, Location, Rack, Cable, Circuit, IPAddress, Prefix):
            ct = ContentType.objects.get_for_model(model_cls)
            if not demo_tag.content_types.filter(pk=ct.pk).exists():
                demo_tag.content_types.add(ct)

        # -- Statuses --
        active_status = _get_or_create_status("Active", Device)
        for cls in (Location, Rack, Cable, Circuit, IPAddress, Prefix):
            _get_or_create_status("Active", cls)
        connected_status = _get_or_create_status("Connected", Cable, color="4caf50")

        # -- Namespace --
        namespace, _ = Namespace.objects.get_or_create(name="Global")

        # -- LocationType --
        site_type, _ = LocationType.objects.get_or_create(name="Site", defaults={"nestable": False})
        for cls in (Device, Rack):
            ct = ContentType.objects.get_for_model(cls)
            if not site_type.content_types.filter(pk=ct.pk).exists():
                site_type.content_types.add(ct)

        location_status = _get_or_create_status("Active", Location)

        # -- Manufacturers & DeviceTypes --
        device_type_map = {}
        for dt_def in DEVICE_TYPES:
            mfr, _ = Manufacturer.objects.get_or_create(name=dt_def["manufacturer"])
            device_type, created = DeviceType.objects.get_or_create(
                manufacturer=mfr,
                model=dt_def["model"],
                defaults={"u_height": dt_def["u_height"]},
            )
            device_type_map[dt_def["model"]] = device_type

            if created:
                for iface_def in dt_def["interfaces"]:
                    name_tpl, iface_type, count = iface_def[0], iface_def[1], iface_def[2]
                    start = iface_def[3] if len(iface_def) > 3 else 1
                    for idx in range(start, start + count):
                        InterfaceTemplate.objects.get_or_create(
                            device_type=device_type,
                            name=name_tpl.format(idx),
                            defaults={"type": iface_type},
                        )
                # Add a management interface template
                InterfaceTemplate.objects.get_or_create(
                    device_type=device_type,
                    name="Management0",
                    defaults={"type": InterfaceTypeChoices.TYPE_1GE_FIXED, "mgmt_only": True},
                )

        self.stdout.write(f"  Created {len(device_type_map)} device types")

        # -- Roles --
        role_map = {}
        for role_def in ROLES:
            role_map[role_def["name"]] = _get_or_create_role(
                role_def["name"], Device, color=role_def["color"], description=role_def["description"]
            )
        self.stdout.write(f"  Created {len(role_map)} roles")

        # -- Locations, Racks, Devices --
        all_devices = {}  # keyed by device name
        interface_ct = ContentType.objects.get_for_model(Interface)
        rack_status = _get_or_create_status("Active", Rack)

        for site_idx, site_def in enumerate(SITES):
            location, _ = Location.objects.get_or_create(
                name=site_def["name"],
                location_type=site_type,
                defaults={"status": location_status, "description": site_def["description"]},
            )
            location.tags.add(demo_tag)
            self.stdout.write(f"  Location: {location.name}")

            # Create 2 racks per site
            racks = []
            for r in range(1, 3):
                rack, _ = Rack.objects.get_or_create(
                    name=f"{site_def['name']}-Rack-{r}",
                    location=location,
                    defaults={"status": rack_status, "u_height": 42},
                )
                rack.tags.add(demo_tag)
                racks.append(rack)

            # Create devices
            rack_idx = 0
            position_tracker = {r.pk: 1 for r in racks}
            for name_tpl, role_name, dt_model, count in SITE_DEVICES:
                for i in range(1, count + 1):
                    dev_name = name_tpl.format(site=site_def["name"].lower(), i=i)
                    device_type = device_type_map[dt_model]
                    rack = racks[rack_idx % len(racks)]
                    pos = position_tracker[rack.pk]
                    position_tracker[rack.pk] += device_type.u_height

                    device, _ = Device.objects.get_or_create(
                        name=dev_name,
                        defaults={
                            "device_type": device_type,
                            "role": role_map[role_name],
                            "location": location,
                            "status": active_status,
                            "rack": rack,
                            "position": pos,
                            "face": "front",
                        },
                    )
                    device.tags.add(demo_tag)
                    all_devices[dev_name] = device
                    rack_idx += 1

            self.stdout.write(f"    Created devices for {site_def['name']}")

            # -- Management IP per device --
            mgmt_prefix_str = MGMT_PREFIXES[site_idx]
            ip_status = _get_or_create_status("Active", IPAddress)
            prefix_status = _get_or_create_status("Active", Prefix)

            mgmt_prefix, _ = Prefix.objects.get_or_create(
                prefix=mgmt_prefix_str,
                namespace=namespace,
                defaults={"status": prefix_status, "type": "network"},
            )
            mgmt_prefix.tags.add(demo_tag)

            host_octet = 10
            site_devices = [d for name, d in all_devices.items() if name.startswith(site_def["name"].lower())]
            for device in site_devices:
                mgmt_iface = device.interfaces.filter(name="Management0").first()
                if mgmt_iface:
                    base = mgmt_prefix_str.split("/")[0].rsplit(".", 1)[0]
                    ip_addr = f"{base}.{host_octet}/24"
                    ip, created = IPAddress.objects.get_or_create(
                        address=ip_addr,
                        parent=mgmt_prefix,
                        defaults={"status": ip_status, "type": "host"},
                    )
                    if created:
                        ip.tags.add(demo_tag)
                        IPAddressToInterface.objects.get_or_create(
                            ip_address=ip,
                            interface=mgmt_iface,
                        )
                    host_octet += 1

        self.stdout.write(f"  Total devices: {len(all_devices)}")

        # ------------------------------------------------------------------
        # Cabling — spine-leaf fabric per site
        # ------------------------------------------------------------------
        cable_count = 0

        for site_def in SITES:
            site_prefix = site_def["name"].lower()
            spines = [all_devices[f"{site_prefix}-spine-{i}"] for i in range(1, 3)]
            leafs = [all_devices[f"{site_prefix}-leaf-{i}"] for i in range(1, 5)]

            # Each spine connects to every leaf (full mesh)
            spine_port_idx = {s.pk: 1 for s in spines}
            for spine in spines:
                for leaf_idx, leaf in enumerate(leafs):
                    spine_iface = spine.interfaces.filter(
                        name=f"Ethernet1/{spine_port_idx[spine.pk]}"
                    ).first()
                    # Leaf uplinks use ports 49+ (40GE)
                    uplink_port = 49 + (spines.index(spine))
                    leaf_iface = leaf.interfaces.filter(name=f"Ethernet{uplink_port}").first()

                    if spine_iface and leaf_iface:
                        cable = Cable.objects.create(
                            termination_a_type=interface_ct,
                            termination_a_id=spine_iface.pk,
                            termination_b_type=interface_ct,
                            termination_b_id=leaf_iface.pk,
                            status=connected_status,
                            label=f"{spine.name}:{spine_iface.name} <-> {leaf.name}:{leaf_iface.name}",
                        )
                        cable.tags.add(demo_tag)
                        cable_count += 1

                    spine_port_idx[spine.pk] += 1

        self.stdout.write(f"  Created {cable_count} spine-leaf cables")

        # ------------------------------------------------------------------
        # Cabling — inter-site WAN links (border routers)
        # ------------------------------------------------------------------
        wan_cable_count = 0
        nyc_borders = [all_devices[f"nyc-dc1-border-{i}"] for i in range(1, 3)]
        lax_borders = [all_devices[f"lax-dc1-border-{i}"] for i in range(1, 3)]

        # Point-to-point /31 prefixes for WAN links
        wan_prefix, _ = Prefix.objects.get_or_create(
            prefix="172.16.0.0/24",
            namespace=namespace,
            defaults={"status": prefix_status, "type": "container"},
        )
        wan_prefix.tags.add(demo_tag)

        wan_octet = 0
        for idx in range(2):
            nyc_border = nyc_borders[idx]
            lax_border = lax_borders[idx]

            nyc_iface = nyc_border.interfaces.filter(name="TenGigE0/0/0/1").first()
            lax_iface = lax_border.interfaces.filter(name="TenGigE0/0/0/1").first()

            if nyc_iface and lax_iface:
                cable = Cable.objects.create(
                    termination_a_type=interface_ct,
                    termination_a_id=nyc_iface.pk,
                    termination_b_type=interface_ct,
                    termination_b_id=lax_iface.pk,
                    status=connected_status,
                    label=f"WAN: {nyc_border.name} <-> {lax_border.name}",
                    color="ff5722",
                )
                cable.tags.add(demo_tag)
                wan_cable_count += 1

                # Assign /31 IPs to WAN interfaces
                p2p_prefix, _ = Prefix.objects.get_or_create(
                    prefix=f"172.16.0.{wan_octet}/31",
                    namespace=namespace,
                    defaults={"status": prefix_status, "type": "network"},
                )
                p2p_prefix.tags.add(demo_tag)

                for offset, iface in enumerate([nyc_iface, lax_iface]):
                    ip, created = IPAddress.objects.get_or_create(
                        address=f"172.16.0.{wan_octet + offset}/31",
                        parent=p2p_prefix,
                        defaults={"status": ip_status, "type": "host"},
                    )
                    if created:
                        ip.tags.add(demo_tag)
                        IPAddressToInterface.objects.get_or_create(ip_address=ip, interface=iface)

                wan_octet += 2

        self.stdout.write(f"  Created {wan_cable_count} WAN cables")

        # ------------------------------------------------------------------
        # Cabling — border routers to spines (uplinks within each site)
        # ------------------------------------------------------------------
        uplink_count = 0
        for site_def in SITES:
            site_prefix = site_def["name"].lower()
            borders = [all_devices[f"{site_prefix}-border-{i}"] for i in range(1, 3)]
            spines = [all_devices[f"{site_prefix}-spine-{i}"] for i in range(1, 3)]

            for b_idx, border in enumerate(borders):
                for s_idx, spine in enumerate(spines):
                    border_port = 2 + s_idx  # TenGigE0/0/0/2 and /3
                    border_iface = border.interfaces.filter(name=f"TenGigE0/0/0/{border_port}").first()
                    spine_port = 5 + b_idx  # Ethernet1/5 and /6 (after leaf ports)
                    spine_iface = spine.interfaces.filter(name=f"Ethernet1/{spine_port}").first()

                    if border_iface and spine_iface:
                        cable = Cable.objects.create(
                            termination_a_type=interface_ct,
                            termination_a_id=border_iface.pk,
                            termination_b_type=interface_ct,
                            termination_b_id=spine_iface.pk,
                            status=connected_status,
                            label=f"{border.name}:{border_iface.name} <-> {spine.name}:{spine_iface.name}",
                        )
                        cable.tags.add(demo_tag)
                        uplink_count += 1

        self.stdout.write(f"  Created {uplink_count} border-to-spine uplink cables")

        # ------------------------------------------------------------------
        # Circuits — WAN circuits between sites via a provider
        # ------------------------------------------------------------------
        circuit_status = _get_or_create_status("Active", Circuit)

        provider, _ = Provider.objects.get_or_create(name="MegaCorp Telecom")
        circuit_type, _ = CircuitType.objects.get_or_create(name="MPLS VPN")

        for idx in range(2):
            circuit, created = Circuit.objects.get_or_create(
                cid=f"WAN-NYC-LAX-{idx + 1}",
                provider=provider,
                defaults={
                    "circuit_type": circuit_type,
                    "status": circuit_status,
                },
            )
            if created:
                circuit.tags.add(demo_tag)
                # A-side: NYC border router
                nyc_border = nyc_borders[idx]
                nyc_iface = nyc_border.interfaces.filter(name="TenGigE0/0/0/4").first()
                if nyc_iface:
                    CircuitTermination.objects.get_or_create(
                        circuit=circuit,
                        term_side="A",
                        defaults={"location": Location.objects.get(name="NYC-DC1")},
                    )
                # Z-side: LAX border router
                lax_border = lax_borders[idx]
                lax_iface = lax_border.interfaces.filter(name="TenGigE0/0/0/4").first()
                if lax_iface:
                    CircuitTermination.objects.get_or_create(
                        circuit=circuit,
                        term_side="Z",
                        defaults={"location": Location.objects.get(name="LAX-DC1")},
                    )

        self.stdout.write(f"  Created 2 WAN circuits")

        # ------------------------------------------------------------------
        # Loopback interfaces and IPs
        # ------------------------------------------------------------------
        loopback_prefix, _ = Prefix.objects.get_or_create(
            prefix="10.255.0.0/24",
            namespace=namespace,
            defaults={"status": prefix_status, "type": "container"},
        )
        loopback_prefix.tags.add(demo_tag)

        lo_octet = 1
        for dev_name, device in all_devices.items():
            iface_status = _get_or_create_status("Active", Interface)
            lo_iface, _ = Interface.objects.get_or_create(
                device=device,
                name="Loopback0",
                defaults={"type": InterfaceTypeChoices.TYPE_VIRTUAL, "status": iface_status},
            )
            ip, created = IPAddress.objects.get_or_create(
                address=f"10.255.0.{lo_octet}/32",
                parent=loopback_prefix,
                defaults={"status": ip_status, "type": "host"},
            )
            if created:
                ip.tags.add(demo_tag)
                IPAddressToInterface.objects.get_or_create(ip_address=ip, interface=lo_iface)
                # Set as primary IP
                device.primary_ip4 = ip
                device.save()
            lo_octet += 1

        self.stdout.write(f"  Assigned loopback IPs to {len(all_devices)} devices")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        total_cables = cable_count + wan_cable_count + uplink_count
        self.stdout.write(self.style.SUCCESS(
            f"\nDemo topology created successfully!\n"
            f"  {len(SITES)} sites, {len(all_devices)} devices, {total_cables} cables, 2 circuits\n"
            f"  All objects tagged with '{DEMO_TAG_NAME}' — use --flush to remove."
        ))
