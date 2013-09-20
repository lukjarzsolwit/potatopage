from django import template


register = template.Library()

@register.simple_tag(takes_context=True)
def paginator_querystring(context, page_number, page_name):
    """ Formats the querystring for the given page number, but keeps the rest of the querystring in tact.
        The page_name argument handles multiple paginators in the same template. The default one is 'page'.
    """
    query_dict = context['request'].GET.copy()
    query_dict[page_name] = page_number
    return query_dict.urlencode()

@register.simple_tag(takes_context=True)
def set_page_name(context):
    """ Defaults the page_name variable to 'page', if there isn't one. """
    if 'page_name' not in context:
        context['page_name'] = 'page'
    return ''

@register.simple_tag(takes_context=True)
def add_to_query_string(context, key, value):
    """ Adds a query to the query string if it exists, otherwise it creates a new one """
    query_string = context['request'].GET.copy()
    query_string[key] = value
    return query_string.urlencode()

@register.simple_tag
def paginator_object_count(page):
    """ Calculate approximate (quick) count of how many objects are in
        full object_list for pagination count """
    if not page.has_next():
        return page_object_count(page)
    else:
        if page.paginator.__class__.__name__ == "DjangoNonrelPaginator" and \
                page.__class__.__name__ == "UnifiedPage":
            last_page = page.paginator._get_final_page()

            if not last_page:
                more_than_string = 'more than'
                prev_page = -2 if len(page.available_pages()) > 1 else -1
                return more_than_string + " %s" % (page.available_pages()[prev_page] * page.paginator.per_page)
            else:
                last_page_obj = page.paginator.page(last_page)
                last_page_count = len(last_page_obj.object_list)
                return "%s" % ((page.paginator._get_known_page_count() - 1) * page.paginator.per_page + last_page_count)

        else:
            # Normal Django Paginator.
            last_page = page.paginator.num_pages

        return last_page * page.paginator.per_page

@register.simple_tag
def page_object_count(page):
    """ Calculate an index of the last element in a current page """
    if page.has_next():
        return page.end_index()
    else:
        # Special case for a last page when the page has less items then a per_page value
        return page.end_index() - page.paginator.per_page + len(page.object_list)
