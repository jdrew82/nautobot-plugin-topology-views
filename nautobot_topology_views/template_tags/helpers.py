from urllib.parse import quote
import json
from django import template
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from nautobot_topology_views.utils import get_selected_values

register = template.Library()


@register.inclusion_tag("helpers/applied_filters.html", takes_context=True)
def applied_filters(context, model, form, query_params):
    """
    Display the active filters for a given filter form.
    """
    user = context["request"].user
    form.is_valid()  # Ensure cleaned_data has been set

    applied_filters = []
    for filter_name in form.changed_data:
        if filter_name not in form.cleaned_data:
            continue

        querydict = query_params.copy()
        if filter_name not in querydict:
            continue

        bound_field = form.fields[filter_name].get_bound_field(form, filter_name)
        querydict.pop(filter_name)
        display_value = ", ".join([str(v) for v in get_selected_values(form, filter_name)])

        applied_filters.append(
            {
                "name": filter_name,
                "value": form.cleaned_data[filter_name],
                "link_url": f"?{querydict.urlencode()}",
                "link_text": f"{bound_field.label}: {display_value}",
            }
        )

    save_link = None
    if user.has_perm("extras.add_savedfilter") and "filter_id" not in context["request"].GET:
        content_type = ContentType.objects.get_for_model(model).pk
        parameters = json.dumps(dict(context["request"].GET.lists()))
        url = reverse("extras:savedfilter_add")
        save_link = f"{url}?content_types={content_type}&parameters={quote(parameters)}"

    return {
        "applied_filters": applied_filters,
        "save_link": save_link,
    }
