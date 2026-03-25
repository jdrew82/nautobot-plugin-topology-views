"""Create fixtures for tests."""

from topology_views.models import RoleImage


def create_roleimage():
    """Fixture to create necessary number of RoleImage for tests."""
    RoleImage.objects.create(name="Test One")
    RoleImage.objects.create(name="Test Two")
    RoleImage.objects.create(name="Test Three")
