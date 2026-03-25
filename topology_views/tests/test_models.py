"""Test RoleImage."""

from nautobot.apps.testing import ModelTestCases

from topology_views import models
from topology_views.tests import fixtures


class TestRoleImage(ModelTestCases.BaseModelTestCase):
    """Test RoleImage."""

    model = models.RoleImage

    @classmethod
    def setUpTestData(cls):
        """Create test data for RoleImage Model."""
        super().setUpTestData()
        # Create 3 objects for the model test cases.
        fixtures.create_roleimage()

    def test_create_roleimage_only_required(self):
        """Create with only required fields, and validate null description and __str__."""
        roleimage = models.RoleImage.objects.create(name="Development")
        self.assertEqual(roleimage.name, "Development")
        self.assertEqual(roleimage.description, "")
        self.assertEqual(str(roleimage), "Development")

    def test_create_roleimage_all_fields_success(self):
        """Create RoleImage with all fields."""
        roleimage = models.RoleImage.objects.create(name="Development", description="Development Test")
        self.assertEqual(roleimage.name, "Development")
        self.assertEqual(roleimage.description, "Development Test")
