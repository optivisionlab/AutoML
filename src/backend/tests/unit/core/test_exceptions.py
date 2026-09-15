# Standard Libraries
import unittest

# Third-party Libraries
from fastapi import status

# Local Libraries
from src.core.exceptions import CustomException
from src.shared.constants import ErrorCode


class TestExceptions(unittest.TestCase):
    def test_custom_exception_initialization(self):
        detail = "Resource not found"
        status_code = status.HTTP_404_NOT_FOUND
        error_code = ErrorCode.NOT_FOUND.value

        exc = CustomException(
            status_code=status_code,
            detail=detail,
            error_code=error_code
        )

        self.assertEqual(exc.status_code, status_code)
        self.assertEqual(exc.detail, detail)
        self.assertEqual(exc.error_code, error_code)
        self.assertEqual(exc.extra, {})
        self.assertEqual(str(exc), "") # Or whatever base exception returns

    def test_custom_exception_with_extra(self):
        extra_data = {"item_id": 123}
        exc = CustomException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bad Request",
            extra=extra_data
        )

        # default error code
        self.assertEqual(exc.error_code, ErrorCode.BAD_REQUEST.value)
        self.assertEqual(exc.extra, extra_data)


if __name__ == '__main__':
    unittest.main()
