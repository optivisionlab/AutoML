# Standard Libraries
import logging

# Third-party Libraries
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from fastapi import Request

# Local Libraries
from src.config.settings import settings


# Logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Contains settings for connecting to the database management system. (Only Connection)
    """
    client: AsyncMongoClient = None
    db: AsyncDatabase = None

    @classmethod
    async def connection(cls) -> None:
        if cls.client is not None:
            return

        logger.info("Initializing MongoDB connection...")
        try:
            mongodb_address = settings.MONGODB.CONNECT

            if not mongodb_address.startswith("mongodb://") and not mongodb_address.startswith("mongodb+srv://"):
                mongodb_address = f"mongodb://{mongodb_address}"

            # Initialization
            cls.client = AsyncMongoClient(
                mongodb_address,
                serverSelectionTimeoutMS=5000,
            )

            # Ping to check server connection
            await cls.client.admin.command('ping')

            # Initialize database instance
            db_name = settings.MONGODB.NAME
            cls.db = cls.client.get_database(db_name)

            logger.info(f"MongoDB connection established successfully to database: {db_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise e

    @classmethod
    async def close_connection(cls) -> None:
        """
        Close the connection to the database when shutting down the application.
        """
        if cls.client is not None:
            logger.info("Closing MongoDB connection pool...")
            await cls.client.close()
            cls.client = None
            cls.db = None
            logger.info("MongoDB connection closed successfully.")


async def get_db(request: Request) -> AsyncDatabase:
    """
    Dependency returns an instance of the database.
    """
    if hasattr(request.app.state, "db") and request.app.state.db is not None:
        return request.app.state.db

    return DatabaseManager.db
