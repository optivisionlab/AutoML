# Standard Libraries
from pathlib import Path

# Third-party Libraries
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class MinIOSettings(BaseModel):
    ENDPOINT: str = "localhost:9000"
    ACCESS_KEY: str = "admin"
    SECRET_KEY: str = "password"

class MongoDB(BaseModel):
    CONNECT: str = "localhost:27017"
    NAME: str = "AutoML"

class ProjectInfo(BaseModel):
    NAME: str = "HAutoML"
    VERSION: str = "0.3.0"
    ENVIRONMENT: str = "development"


class Settings(BaseSettings):
    """
    Centralized configuration management for project
    """
    # System Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

    # Project Info
    PROJECT: ProjectInfo = ProjectInfo()

    # Address
    HOST_BACK_END: str = "0.0.0.0"
    PORT_BACK_END: int = 9999

    # Database Settings
    MONGODB: MongoDB = MongoDB()

    # Minio Settings
    MINIO: MinIOSettings = MinIOSettings()

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        env_nested_delimiter="_",
        extra="ignore"
    )


# Instantiate the settings object to be used across the application
settings = Settings()
