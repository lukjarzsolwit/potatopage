from django.db import models
from django.test import TestCase

import mock

from potatopage.paginator import GaeUnifiedPaginator, EmptyPage


class PaginationModel(models.Model):
    field1 = models.IntegerField()


class UnifiedPaginatorTests(TestCase):
    def setUp(self):
        for i in xrange(12):
            PaginationModel.objects.create(field1=i)

    def test_basic_usage(self):
        paginator = GaeUnifiedPaginator(PaginationModel.objects.all().order_by("field1"), 5)

        page1 = paginator.page(1)
        self.assertEqual(5, len(page1.object_list))
        self.assertEqual(0, page1.object_list[0].field1)
        self.assertTrue(page1.has_next())
        self.assertFalse(page1.has_previous())
        self.assertEqual([1, 2], page1.available_pages())

        page2 = paginator.page(2)
        self.assertEqual(5, len(page2.object_list))
        self.assertEqual(5, page2.object_list[0].field1)
        self.assertTrue(page2.has_next())
        self.assertTrue(page2.has_previous())
        self.assertEqual([1, 2, 3], page2.available_pages())

        page3 = paginator.page(3)
        self.assertEqual(2, len(page3.object_list))
        self.assertEqual(10, page3.object_list[0].field1)
        self.assertFalse(page3.has_next())
        self.assertTrue(page3.has_previous())
        self.assertEqual([2, 3], page3.available_pages())

        self.assertRaises(EmptyPage, paginator.page, 4)

    def test_cursor_caching(self):
        paginator = GaeUnifiedPaginator(PaginationModel.objects.all().order_by("field1"), 5, batch_size=2)

        paginator.page(3)

        self.assertFalse(paginator.has_cursor_for_page(2))
        self.assertFalse(paginator.has_cursor_for_page(3))
        self.assertTrue(paginator.has_cursor_for_page(5))

        paginator.page(1)
        self.assertFalse(paginator.has_cursor_for_page(2))
        self.assertTrue(paginator.has_cursor_for_page(3))
        self.assertTrue(paginator.has_cursor_for_page(5))

        with mock.patch("potatopage.paginator.GaeUnifiedPaginator._process_batch_hook") as mock_obj:
            #Should now use the cached cursor
            page3 = paginator.page(3)
            #Should have been called with a cursor as the 3rd argument
            self.assertTrue(mock_obj.call_args[0][2])

        self.assertEqual(2, len(page3.object_list))
        self.assertEqual(10, page3.object_list[0].field1)

    def test_in_query(self):
        paginator = GaeUnifiedPaginator(PaginationModel.objects.filter(field1__in=xrange(12)).all().order_by("field1"), 5)

        page1 = paginator.page(1)
        self.assertEqual(5, len(page1.object_list))
        self.assertEqual(0, page1.object_list[0].field1)
        self.assertTrue(page1.has_next())
        self.assertFalse(page1.has_previous())
        self.assertEqual([1, 2], page1.available_pages())

        page2 = paginator.page(2)
        self.assertEqual(5, len(page2.object_list))
        self.assertEqual(5, page2.object_list[0].field1)
        self.assertTrue(page2.has_next())
        self.assertTrue(page2.has_previous())
        self.assertEqual([1, 2, 3], page2.available_pages())

        page3 = paginator.page(3)
        self.assertEqual(2, len(page3.object_list))
        self.assertEqual(10, page3.object_list[0].field1)
        self.assertFalse(page3.has_next())
        self.assertTrue(page3.has_previous())
        self.assertEqual([2, 3], page3.available_pages())

        self.assertRaises(EmptyPage, paginator.page, 4)
