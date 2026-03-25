"""Unit tests for topology_views."""

from nautobot.apps.testing import APIViewTestCases

from topology_views import models
from topology_views.tests import fixtures


class RoleImageAPIViewTest(APIViewTestCases.APIViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the API viewsets for RoleImage."""

    model = models.RoleImage
    # Any choice fields will require the choices_fields to be set
    # to the field names in the model that are choice fields.
    choices_fields = ()

    @classmethod
    def setUpTestData(cls):
        """Create test data for RoleImage API viewset."""
        super().setUpTestData()
        # Create 3 objects for the generic API test cases.
        fixtures.create_roleimage()
        # Create 3 objects for the api test cases.
        cls.create_data = [
            {
                "name": "API Test One",
                "description": "Test One Description",
            },
            {
                "name": "API Test Two",
                "description": "Test Two Description",
            },
            {
                "name": "API Test Three",
                "description": "Test Three Description",
            },
        ]
        cls.update_data = {
            "name": "Update Test Two",
            "description": "Test Two Description",
        }
        cls.bulk_update_data = {
            "description": "Test Bulk Update Description",
        }
