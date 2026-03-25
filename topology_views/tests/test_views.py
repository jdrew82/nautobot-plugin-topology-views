"""Unit tests for views."""

from nautobot.apps.testing import ViewTestCases

from topology_views import models
from topology_views.tests import fixtures


class RoleImageViewTest(ViewTestCases.PrimaryObjectViewTestCase):
    # pylint: disable=too-many-ancestors
    """Test the RoleImage views."""

    model = models.RoleImage
    bulk_edit_data = {"description": "Bulk edit views"}
    form_data = {
        "name": "Test 1",
        "description": "Initial model",
    }

    update_data = {
        "name": "Test 2",
        "description": "Updated model",
    }

    @classmethod
    def setUpTestData(cls):
        fixtures.create_roleimage()
