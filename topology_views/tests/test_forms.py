"""Test roleimage forms."""

from django.test import TestCase

from topology_views import forms


class RoleImageTest(TestCase):
    """Test RoleImage forms."""

    def test_specifying_all_fields_success(self):
        form = forms.RoleImageForm(
            data={
                "name": "Development",
                "description": "Development Testing",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertTrue(form.save())

    def test_specifying_only_required_success(self):
        form = forms.RoleImageForm(
            data={
                "name": "Development",
            }
        )
        self.assertTrue(form.is_valid())
        self.assertTrue(form.save())

    def test_validate_name_roleimage_is_required(self):
        form = forms.RoleImageForm(data={"description": "Development Testing"})
        self.assertFalse(form.is_valid())
        self.assertIn("This field is required.", form.errors["name"])
