# Standard Libraries
import logging
from contextlib import asynccontextmanager

# Third-party Libraries
import uvicorn
from fastapi import FastAPI

# Local Libraries
from src.config.settings import settings
from src.config.logging import setup_logging
from src.config.database import DatabaseManager
from src.core.middlewares import setup_middlewares
from src.core.exceptions import setup_exception_handlers
from src.modules.auth.router import router as auth


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
setup_middlewares(app=app)

# Enable error normalization
setup_exception_handlers(app=app)

# APIs
app.include_router(auth, prefix="/api/v1")


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
