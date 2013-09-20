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
        return page.end_index()
    else:
        if page.paginator.__class__.__name__ == "DjangoNonrelPaginator" and \
                page.__class__.__name__ == "UnifiedPage":
            last_page = page.paginator._get_final_page()

            if not last_page:
                more_than_string = 'more than'
                return more_than_string + " %s" % page.known_end_index()
            else:
                return page.last_page_end_index()

        else:
            # Normal Django Paginator.
            last_page = page.paginator.num_pages

        return last_page * page.paginator.per_page

