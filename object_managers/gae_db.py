from djangoappengine.db.utils import set_cursor, get_cursor

from ..utils import supports_cursor
from .base import ObjectManager


class DjangoNonrelManager(ObjectManager):
    """
        Object manager handling normal GAE db querysets.

        TODO: Somre more specific manager tests would be nice. Not that
              necessary though.
    """
    def __init__(self, queryset):
        self.queryset = queryset
        self.supports_cursors = supports_cursor(queryset)
        self._start_cursor = None
        self._latest_cursor = None

    @property
    def cache_key(self):
        return " ".join([
            str(self.queryset.query.where),
            str(self.queryset.query.order_by),
            str(self.queryset.query.low_mark),
            str(self.queryset.query.high_mark)
        ]).replace(" ", "_")

    def starting_cursor(self, cursor):
        self._start_cursor = cursor
        self._latest_cursor = None

    @property
    def next_cursor(self):
        return self._latest_cursor

    def __getitem__(self, value):
        query = self.queryset.all()[value]
        if self._start_cursor:
            query = set_cursor(query, start=self._start_cursor)
            self._start_cursor = None

        obj_list = list(query)
        try:
            self._latest_cursor = get_cursor(query)
        except TypeError:
            # get_cursor() tries to call .urlsafe() on the cursor with fails
            # if the cursor is None. So we save None if it's None. Makes sense.
            self._latest_cursor = None

        return obj_list

    def contains_more_objects(self, next_batch_cursor):
        query = self.queryset.all().values_list('pk')
        query = set_cursor(query, start=next_batch_cursor)

        try:
            query[0]
            return True
        except IndexError:
            return False
