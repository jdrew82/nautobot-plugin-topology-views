"""Custom template tags for nautobot_topology_views."""

from django import template
from django.urls import NoReverseMatch, reverse

from nautobot_topology_views.utils import get_selected_values

register = template.Library()


@register.inclusion_tag("nautobot_topology_views/inc/applied_filters.html", takes_context=True)
def applied_filters(context, model, form, query_params):
    """Display the active filters for a given filter form."""
    user = context["request"].user
    form.is_valid()  # Ensure cleaned_data has been set

    active_filters = []
    for filter_name in form.changed_data:
        if filter_name not in form.cleaned_data:
            continue

        querydict = query_params.copy()
        if filter_name not in querydict:
            continue

        bound_field = form.fields[filter_name].get_bound_field(form, filter_name)
        querydict.pop(filter_name)
        display_value = ", ".join([str(v) for v in get_selected_values(form, filter_name)])

        active_filters.append(
            {
                "name": filter_name,
                "value": form.cleaned_data[filter_name],
                "link_url": f"?{querydict.urlencode()}",
                "link_text": f"{bound_field.label}: {display_value}",
            }
        )

    # Nautobot 3 replaced Saved Filters with Saved Views (extras:savedview_*). Creating a view
    # requires POST from the list-view modal, so we only link to management UI here.
    saved_views_link = None
    if user.has_perm("extras.view_savedview") and "saved_view" not in context["request"].GET:
        try:
            saved_views_link = reverse("extras:savedview_list")
        except NoReverseMatch:
            saved_views_link = None

    return {
        "applied_filters": active_filters,
        "saved_views_link": saved_views_link,
    }
