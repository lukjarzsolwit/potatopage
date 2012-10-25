import logging

from django.core.cache import cache
from django.core.paginator import (
    Paginator,
    EmptyPage,
    PageNotAnInteger,
    Page
)

from djangoappengine.db.utils import set_cursor, get_cursor

try:
    from datastore_utils.get_in_batches import supports_cursor
except ImportError:
    from libs.datastore_utils.get_in_batches import supports_cursor

class CursorNotFound(Exception):
    pass

class UnifiedPaginator(Paginator):
    def __init__(self, queryset, per_page, batch_size=1, readahead=True, *args, **kwargs):
        """
            batch_size - The steps (in pages) that cursors are cached. A batch_size
            of 1 means that a cursor is cached for the start of each page.

            readahead - When we store a cursor, try to access it to see if there is
            anything actually there. This makes page counts behave correctly at the
            cost of an extra keys_only query using the cursor as an offset. This isn't
            used on IN queries as that would be slow as molasses
        """

        self._queryset = queryset
        self._batch_size = batch_size
        self._query_supports_cursors = supports_cursor(queryset)
        self._readahead = readahead

        if not self._query_supports_cursors:
            self._readahead = False

        self._query_key = " ".join([
            str(queryset.query.where),
            str(queryset.query.order_by),
            str(queryset.query.low_mark),
            str(queryset.query.high_mark)
        ]).replace(" ", "_")

        super(UnifiedPaginator, self).__init__(None, per_page, *args, **kwargs)

    def _get_known_page_count(self):
        key = "|".join([self._query_key, "KNOWN_MAX"])
        return cache.get(key)

    def _put_known_page_count(self, count):
        key = "|".join([self._query_key, "KNOWN_MAX"])
        return cache.set(key, count)

    def _put_cursor(self, zero_based_page, cursor):
        if not self._query_supports_cursors:
            return

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

        offset = 0
        cursor = None
        page_with_cursor = self._find_nearest_page_with_cursor(page)

        if self._query_supports_cursors:
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
            query = self._queryset.all()[:(self.per_page * self._batch_size)]
            query = set_cursor(query, start=cursor)
        else:
            bottom = (self.per_page * self._find_nearest_page_with_cursor(number-1))
            top = bottom + (self.per_page * self._batch_size)
            #No cursor, so grab the full batch
            query = self._queryset.all()[bottom:top]

        results = list(query) #Get the results
        self._process_batch_hook(results, number-1, cursor, offset)

        nearest_page_with_cursor = self._find_nearest_page_with_cursor(number-1)
        next_cursor = None
        if self._query_supports_cursors:
            #Store the cursor at the start of the NEXT batch
            next_cursor = get_cursor(query)
            self._put_cursor(nearest_page_with_cursor + self._batch_size, next_cursor)

        batch_result_count = len(results)

        actual_results = results[offset:offset + self.per_page]

        if not actual_results:
            if number == 1 and self.allow_empty_first_page:
                pass
            else:
                raise EmptyPage('That page contains no results')

        known_page_count = nearest_page_with_cursor + (batch_result_count // self.per_page)

        if known_page_count >= self._get_known_page_count():
            if next_cursor and self._readahead:
                query = self._queryset.all().values_list('pk')
                query = set_cursor(query, start=next_cursor)
                try:
                    query[0]
                except IndexError:
                    pass
                else:
                    known_page_count += 1
            elif batch_result_count == self._batch_size * self.per_page:
                # If we got back exactly the right amount, we assume there is at least
                # one more page.
                known_page_count += 1

            self._put_known_page_count(known_page_count)

        return UnifiedPage(actual_results, number, self)

    def _get_count(self):
        raise NotImplemented("Not available in %s" % self.__class__.__name__)

    def _get_num_pages(self):
        raise NotImplemented("Not available in %s" % self.__class__.__name__)

class UnifiedPage(Page):
    def __init__(self, object_list, number, paginator):
        super(UnifiedPage, self).__init__(object_list, number, paginator)

    def has_next(self):
        return self.number < self.paginator._get_known_page_count()

    def end_index(self):
        """ Override to prevent a call to _get_count """
        return self.number * self.paginator.per_page

    def available_pages(self, limit_to_batch_size=True):
        """
            Returns a list of sorted integers that represent the
            pages that should be displayed in the paginator. In relation to the
            current page. For example, if this page is page 3, and batch_size is 5
            we get the following:

            [ 1, 2, *3*, 4, 5, 6, 7, 8 ]

            If we then choose page 7, we get this:

            [ 2, 3, 4, 5, 6, *7*, 8, 9, 10, 11, 12 ]

            If limit_to_batch_size is False, then you always get all known pages
            this will generally be the same for the upper count, but the results
            will always start at 1.
        """
        min_page = (self.number - self.paginator._batch_size) if limit_to_batch_size else 1
        if min_page < 1:
            min_page = 1

        max_page = min(self.number + self.paginator._batch_size, self.paginator._get_known_page_count())
        return list(xrange(min_page, max_page + 1))

