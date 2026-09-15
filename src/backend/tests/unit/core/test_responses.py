# Standard Libraries
import unittest

# Third-party Libraries
from pydantic import ValidationError

# Local Libraries
from src.core.responses import BaseResponse, PaginatedResponse, OffsetPaginatedResponse
from src.shared.constants import MessageResponse


class TestResponses(unittest.TestCase):
    def test_base_response_default(self):
        response = BaseResponse()
        self.assertTrue(response.success)
        self.assertEqual(response.message, MessageResponse.SUCCESS.value)
        self.assertIsNone(response.data)
        self.assertIsNone(response.meta)

    def test_base_response_with_data(self):
        data = {"id": 1, "name": "Test"}
        response = BaseResponse(data=data)
        self.assertTrue(response.success)
        self.assertEqual(response.data, data)

    def test_paginated_response(self):
        data = [{"id": 1}, {"id": 2}]
        meta = {
            "total_items": 100,
            "current_page": 1,
            "page_size": 2,
            "total_pages": 50
        }

        response = PaginatedResponse(data=data, meta=meta)
        self.assertTrue(response.success)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.meta.total_items, 100)
        self.assertEqual(response.meta.current_page, 1)

    def test_paginated_response_validation_error(self):
        data = [{"id": 1}]
        # Missing required fields in meta
        meta = {"total_items": 100} 

        with self.assertRaises(ValidationError):
            PaginatedResponse(data=data, meta=meta)

    def test_offset_paginated_response(self):
        data = [{"id": 1}]
        meta = {
            "offset": 0,
            "limit": 10,
            "total_items": 5,
            "has_more": False
        }

        response = OffsetPaginatedResponse(data=data, meta=meta)
        self.assertTrue(response.success)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.meta.offset, 0)
        self.assertFalse(response.meta.has_more)


if __name__ == '__main__':
    unittest.main()
