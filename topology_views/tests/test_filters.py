"""Test RoleImage Filter."""

from nautobot.apps.testing import FilterTestCases

from topology_views import filters, models
from topology_views.tests import fixtures


class RoleImageFilterTestCase(FilterTestCases.FilterTestCase):  # pylint: disable=too-many-ancestors
    """RoleImage Filter Test Case."""

    queryset = models.RoleImage.objects.all()
    filterset = filters.RoleImageFilterSet
    generic_filter_tests = (
        ("id",),
        ("created",),
        ("last_updated",),
        ("name",),
    )

    @classmethod
    def setUpTestData(cls):
        """Setup test data for RoleImage Model."""
        fixtures.create_roleimage()

    def test_q_search_name(self):
        """Test using Q search with name of RoleImage."""
        params = {"q": "Test One"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 1)

    def test_q_invalid(self):
        """Test using invalid Q search for RoleImage."""
        params = {"q": "test-five"}
        self.assertEqual(self.filterset(params, self.queryset).qs.count(), 0)
