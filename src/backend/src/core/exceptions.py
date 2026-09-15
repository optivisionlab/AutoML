# Standard Libraries
from typing import Any

# Third-party Libraries
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Local Libraries
from src.shared.constants import ErrorCode


class CustomException(Exception):
    """
    Base exception class for the application
    """
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = ErrorCode.BAD_REQUEST.value,
        extra: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.extra = extra or {}


def setup_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        """
        Catch the business logic errors
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error_code": exc.error_code,
                "detail": exc.detail,
                "extra": exc.extra,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Reformatting Pydantic's validate error
        """
        formatted_errors = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            formatted_errors.append({
                "field": field, 
                "message": err.get("msg")
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "Invalid input data",
                "extra": {"errors": formatted_errors},
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Catch all application crash errors (HTTP 500)
        """        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error_code": ErrorCode.INTERNAL_SERVER_ERROR.value,
                "detail": "The system is experiencing issues, please try again later.",
            },
        )
