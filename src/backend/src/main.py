# Standard Libraries
import logging
from contextlib import asynccontextmanager

# Third-party Libraries
import uvicorn
from fastapi import FastAPI

# Local Libraries
from src.core import middlewares, exceptions
from src.config import settings, setup_logging, databases
from src.shared import mqtt_service, kafka_service, minio_service
from src.modules.auth import auth
from src.modules.users import users
from src.modules.datasets import datasets
from src.modules.notifications import notifications
from src.modules.inference import inference


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
    await databases.DatabaseManager.connection()
    
    # Bring the database instance into the FastAPI state.
    app.state.db = databases.DatabaseManager.db

    # MQTT connection
    await mqtt_service.connect()

    # Kafka connection
    await kafka_service.connect()

    yield

    # Application shutdown process
    await databases.DatabaseManager.close_connection()
    await mqtt_service.disconnect()
    await kafka_service.disconnect()
    await minio_service.close()


# Initialize Application
app = FastAPI(
    title=settings.PROJECT.NAME,
    version=settings.PROJECT.VERSION,
    lifespan=lifespan,
    description="Backend API for HAutoML project.",
)


# Cross-Origin Resource Sharing
middlewares.setup_middlewares(app=app)

# Enable error normalization
exceptions.setup_exception_handlers(app=app)

# APIs
app.include_router(auth, prefix="/api/v1")
app.include_router(users, prefix="/api/v1")
app.include_router(notifications, prefix="/api/v1")
app.include_router(datasets, prefix="/api/v1")
app.include_router(inference, prefix="/api/v1")


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
