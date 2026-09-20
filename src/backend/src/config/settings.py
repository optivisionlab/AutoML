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


class JWTSettings(BaseModel):
    SECRET_KEY: str = "secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_EXPIRE: int = 15
    REFRESH_EXPIRE: int = 7


class MailSettings(BaseModel):
    USERNAME: str = "username"
    PASSWORD: str = "password"


class GoogleSettings(BaseModel):
    CLIENT_ID: str = "client_id"
    CLIENT_SECRET: str = "client_secret"


class MQTTSettings(BaseModel):
    HOSTNAME: str = "localhost"
    PORT: int = 1883
    USERNAME: str = "admin"
    PASSWORD: str = "password"


class KafkaSettings(BaseModel):
    SERVER: str = "localhost:9092"
    TOPIC: str = "train-job-topic"


class Settings(BaseSettings):
    """
    Centralized configuration management for project
    """
    # System Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    LOGO: str = "https://"

    # Project Info
    PROJECT: ProjectInfo = ProjectInfo()

    # Address
    HOST_BACK_END: str = "0.0.0.0"
    PORT_BACK_END: int = 9999

    # Domain
    FRONTEND_URL: str = "http://localhost:3000"
    REDIRECT_URI: str = "http://localhost:9999"

    # Database Settings
    MONGODB: MongoDB = MongoDB()

    # Minio Settings
    MINIO: MinIOSettings = MinIOSettings()

    # JWT Settings
    JWT: JWTSettings = JWTSettings()

    # Mail Settings
    MAIL: MailSettings = MailSettings()

    # Google Settings
    GOOGLE: GoogleSettings = GoogleSettings()

    # MQTT Settings
    MQTT: MQTTSettings = MQTTSettings()

    # Kafka Settings
    KAFKA: KafkaSettings = KafkaSettings()

    # List of allowed API sources
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",      # React/Next.js local
        "http://localhost:5173",      # Vite local
    ]

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        env_nested_delimiter="_",
        extra="ignore"
    )


# Instantiate the settings object to be used across the application
settings = Settings()
