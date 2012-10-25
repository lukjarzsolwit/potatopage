import logging

from django.core.cache import cache
from django.core.paginator import (
    Paginator,
    EmptyPage,
    PageNotAnInteger,
    Page
)

from djangoappengine.db.utils import set_cursor, get_cursor

class CursorNotFound(Exception):
    pass

class UnifiedPaginator(Paginator):
    def __init__(self, queryset, per_page, batch_size=1, *args, **kwargs):
        """
            batch_size - The steps (in pages) that cursors are cached. A batch_size
            of 1 means that a cursor is cached for the start of each page.
        """

        self._queryset = queryset
        self._batch_size = batch_size
        self._query_supports_cursors = True #FIXME
        self._query_key = " ".join([
            str(queryset.query.where),
            str(queryset.query.order_by),
            str(queryset.query.low_mark),
            str(queryset.query.high_mark)
        ]).replace(" ", "_")

        super(UnifiedPaginator, self).__init__(None, per_page, *args, **kwargs)

    def _put_cursor(self, page, cursor):
        key = "|".join([self._query_key, str(page)])
        cache.set(key, cursor)

    def _get_cursor(self, page):
        key = "|".join([self._query_key, str(page)])
        return cache.get(key)

    def validate_number(self, number):
        "Validates the given 1-based page number."
        try:
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger('That page number is not an integer')
        if number < 1:
            raise EmptyPage('That page number is less than 1')

        return number

    def _get_cursor_and_offset(self, page):
        """ Returns a cursor and offset for the page. page is zero-based! """
        if not self._query_supports_cursors:
            return None, self.per_page * page

        offset = 0
        cursor = None

        def find_nearest_page_with_cursor(current_page):
            #Find the next page down that should be storing a cursor
            page_with_cursor = current_page
            while page_with_cursor % self._batch_size != 0:
                page_with_cursor -= 1
            return page_with_cursor

        page_with_cursor = find_nearest_page_with_cursor(page)

        try:
            cursor = self._get_cursor(page_with_cursor)
            logging.info("Using existing cursor from memcache")
        except CursorNotFound:
            logging.info("Couldn't find a cursor, creating one")
            #FIXME: This could be much smarter, we could keep going backwards
            #until we find a cursor and then seek forwards. We could also
            #store the cursor at each batch size

            #Cursor wasn't there! So let's seek it out and store it
            query = self._queryset[:page_with_cursor * self.per_page]
            self._put_cursor(page_with_cursor, get_cursor(query))
            cursor = self._get_cursor(page_with_cursor)

        offset = (page - page_with_cursor) * self.per_page

        return cursor, offset

    def page(self, number):
        number = self.validate_number(number)

        cursor, offset = self._get_cursor_and_offset(number-1)

        #Read the entire batch size from the last cursor
        query = self._queryset[:(self.per_page * self._batch_size)]
        query = set_cursor(query, start=cursor)

        results = list(query) #Get the results

        if not results[offset:]:
            if number == 1 and self.allow_empty_first_page:
                pass
            else:
                raise EmptyPage('That page contains no results')

        #Store the cursor on the NEXT page (put_cursor uses zero-based pages)
        #so number is current_page + 1
        self._put_cursor(number, get_cursor(query))

        return Page(results[offset:offset + self.per_page], number, self)

    def _get_count(self):
        raise NotImplemented("Not available in %s" % self.__class__.__name__)

    def _get_num_pages(self):
        raise NotImplemented("Not available in %s" % self.__class__.__name__)

