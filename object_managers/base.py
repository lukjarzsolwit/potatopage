from djangoappengine.db.utils import set_cursor, get_cursor
from potatopage.utils import supports_cursor


class ObjectManager(object):
    supports_cursors = None

    def get_cache_key(self):
        raise NotImplemented()
    cache_key = property(get_cache_key)

    def starting_cursor(self, cursor):
        if self.supports_cursors:
            raise NotImplemented()

    @property
    def next_cursor(self):
        if self.supports_cursors:
            raise NotImplemented()

    def __getitem__(self, value):
        raise NotImplemented()

    def contains_more_objects(self):
        raise NotImplemented()


# All the following stuff will move into a separate file when reviewed.
# We need first to decide if we want to go that way.
class GaeQuerysetWrapper(ObjectManager):

    def __init__(self, queryset):
        self.queryset = queryset
        self.supports_cursors = supports_cursor(queryset)

    def get_cache_key():
        return " ".join([
            str(queryset.query.where),
            str(queryset.query.order_by),
            str(queryset.query.low_mark),
            str(queryset.query.high_mark)
        ]).replace(" ", "_")
    cache_key = property(get_cache_key)

    def starting_cursor(self, cursor):
        self._start_cursor = cursor
        return self

    def __getitem__(self, value):
        query = self.queryset.all()[value]
        if self._start_cursor:
            query = set_cursor(query, start=self._start_cursor)
            self._start_cursor = None

        obj_list = list(query)
        self._cached_query = query
        return obj_list

    @property
    def next_cursor(self):
        if not hasattr(self, "_cached_query"):
            return get_cursor(self._cached_query)

        return None  # Not necessary, just making it clear.

    def contains_more_objects(self, next_batch_cursor):
        query = self.queryset.all().values_list('pk')
        query = set_cursor(query, start=next_page_cursor)

        try:
            query[0]
            return True
        except IndexError:
            return False


