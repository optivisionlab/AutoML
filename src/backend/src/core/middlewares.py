# Standard Libraries
import time

# Third-party Libraries
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Local Libraries
from src.config import settings


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to calculate and log the processing time of each request
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Process-Time"] = str(process_time)
        return response


def setup_middlewares(app: FastAPI) -> None:
    """
    Register all global middlewares to the FastAPI app
    """

    # Set all CORS enabled origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Content-Type", "Authorization", "Accept"]
    )

    app.add_middleware(ProcessTimeMiddleware)
