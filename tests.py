from django.db import models
from django.utils import unittest

from potatopage.paginator import UnifiedPaginator, EmptyPage

class PaginationModel(models.Model):
    field1 = models.IntegerField()

class UnifiedPaginatorTests(unittest.TestCase):
    def setUp(self):
        for i in xrange(12):
            PaginationModel.objects.create(field1=i)

    def test_basic_usage(self):
        paginator = UnifiedPaginator(PaginationModel.objects.all().order_by("field1"), 5)

        page1 = paginator.page(1)
        self.assertEqual(5, len(page1.object_list))
        self.assertEqual(0, page1.object_list[0].field1)

        page2 = paginator.page(2)
        self.assertEqual(5, len(page2.object_list))
        self.assertEqual(5, page2.object_list[0].field1)

        page3 = paginator.page(3)
        self.assertEqual(2, len(page3.object_list))
        self.assertEqual(10, page3.object_list[0].field1)

        self.assertRaises(EmptyPage, paginator.page, 4)

