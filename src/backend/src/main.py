# Standard Libraries
import logging
from contextlib import asynccontextmanager

# Third-party Libraries
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Local Libraries
from src.config.settings import settings
from src.config.database import DatabaseManager
from src.config.logging import setup_logging


# Activate Logging
if not logging.getLogger().handlers:
    setup_logging()


# Lifespan Context Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events
    """
    # Initialize the connection pool to MongoDB.
    await DatabaseManager.connection()
    
    # Bring the database instance into the FastAPI state.
    app.state.db = DatabaseManager.db

    yield

    # Application shutdown process
    await DatabaseManager.close_connection()


# Initialize Application
app = FastAPI(
    title=settings.PROJECT.NAME,
    version=settings.PROJECT.VERSION,
    lifespan=lifespan,
    description="Backend API for HAutoML project.",
)


# Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health Check"])
async def health_check():
    return {
        "project": settings.PROJECT.NAME,
        "version": settings.PROJECT.VERSION,
        "environment": settings.PROJECT.ENVIRONMENT,
        "status": "Running",
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.HOST_BACK_END,
        port=settings.PORT_BACK_END,
        reload=settings.PROJECT.ENVIRONMENT == "development",
    )
