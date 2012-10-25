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

    def _put_cursor(self, zero_based_page, cursor):
        assert cursor
        logging.info("Storing cursor for page: %s" % (zero_based_page))
        key = "|".join([self._query_key, str(zero_based_page)])
        cache.set(key, cursor)

    def _get_cursor(self, zero_based_page):
        logging.info("Getting cursor for page: %s" % (zero_based_page))
        key = "|".join([self._query_key, str(zero_based_page)])
        result = cache.get(key)
        if result is None:
            raise CursorNotFound("No cursor available for %s" % zero_based_page)
        return result

    def has_cursor_for_page(self, page):
        try:
            self._get_cursor(page-1)
            return True
        except CursorNotFound:
            return False

    def validate_number(self, number):
        "Validates the given 1-based page number."
        try:
            number = int(number)
        except (TypeError, ValueError):
            raise PageNotAnInteger('That page number is not an integer')
        if number < 1:
            raise EmptyPage('That page number is less than 1')

        return number

    def _find_nearest_page_with_cursor(self, current_page):
        #Find the next page down that should be storing a cursor
        page_with_cursor = current_page
        while page_with_cursor % self._batch_size != 0:
            page_with_cursor -= 1
        return page_with_cursor

    def _get_cursor_and_offset(self, page):
        """ Returns a cursor and offset for the page. page is zero-based! """
        if not self._query_supports_cursors:
            return None, self.per_page * page

        offset = 0
        cursor = None

        page_with_cursor = self._find_nearest_page_with_cursor(page)
        if page_with_cursor > 0:
            try:
                cursor = self._get_cursor(page_with_cursor)
                logging.info("Using existing cursor from memcache")
            except CursorNotFound:
                logging.info("Couldn't find a cursor")
                #No cursor found, so we just return the offset old-skool-style.
                cursor = None

        offset = (page - page_with_cursor) * self.per_page

        return cursor, offset

    def _process_batch_hook(self, batch_results, zero_based_page, cursor, offset):
        """ Override this in the subclass to cache results etc."""
        pass

    def page(self, number):
        number = self.validate_number(number)

        cursor, offset = self._get_cursor_and_offset(number-1)

        if cursor:
            #Read the entire batch size from the last cursor
            query = self._queryset[:(self.per_page * self._batch_size)]
            query = set_cursor(query, start=cursor)
        else:
            bottom = (self.per_page * self._find_nearest_page_with_cursor(number-1))
            top = bottom + (self.per_page * self._batch_size)
            #No cursor, so grab the full batch
            query = self._queryset[bottom:top]

        results = list(query) #Get the results
        self._process_batch_hook(results, number-1, cursor, offset)

        if not results[offset:]:
            if number == 1 and self.allow_empty_first_page:
                pass
            else:
                raise EmptyPage('That page contains no results')

        #Store the cursor at the start of the NEXT batch
        self._put_cursor(self._find_nearest_page_with_cursor(number-1) + self._batch_size, get_cursor(query))

        return Page(results[offset:offset + self.per_page], number, self)

    def _get_count(self):
        raise NotImplemented("Not available in %s" % self.__class__.__name__)

    def _get_num_pages(self):
        raise NotImplemented("Not available in %s" % self.__class__.__name__)

