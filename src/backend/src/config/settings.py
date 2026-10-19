# Standard Libraries
from pathlib import Path

# Third-party Libraries
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR: Path = Path(__file__).resolve().parents[2]
ENV_FILE: Path = BASE_DIR / ".env"


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


class MinIOSettings(CommonSettings):
    ENDPOINT: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    ACCESS_KEY: str = Field(default="admin", validation_alias="MINIO_ACCESS_KEY")
    SECRET_KEY: str = Field(default="password123", validation_alias="MINIO_SECRET_KEY")


class BackblazeSettings(CommonSettings):
    ACCESS_KEY_ID: str = Field(default="", validation_alias="BACKBLAZE_ACCESS_KEY_ID")
    SECRET_ACCESS_KEY: str = Field(default="", validation_alias="BACKBLAZE_SECRET_ACCESS_KEY")
    ENDPOINT_URL: str = Field(default="", validation_alias="BACKBLAZE_ENDPOINT_URL")
    BUCKET_NAME: str = Field(default="hautoml-storage", validation_alias="BACKBLAZE_BUCKET_NAME")
    MAX_FILE_SIZE_MB: int = Field(default=10, validation_alias="BACKBLAZE_MAX_FILE_SIZE_MB")


class MongoDB(CommonSettings):
    CONNECT: str = Field(default="localhost:27017", validation_alias="MONGODB_CONNECT")
    NAME: str = "AutoML"


class ProjectInfo(CommonSettings):
    NAME: str = "HAutoML"
    VERSION: str = "0.3.0"
    ENVIRONMENT: str = "development"


class JWTSettings(CommonSettings):
    SECRET_KEY: str = Field(default="secret-key", validation_alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", validation_alias="ALGORITHM")
    ACCESS_EXPIRE: int = Field(default=15, validation_alias="ACCESS_EXPIRE")
    REFRESH_EXPIRE: int = Field(default=7, validation_alias="REFRESH_EXPIRE")


class MailSettings(CommonSettings):
    USERNAME: str = Field(default="username", validation_alias="MAIL_USERNAME")
    PASSWORD: str = Field(default="password", validation_alias="MAIL_PASSWORD")
    LOGO: str = Field(default="https://abc.png", validation_alias="MAIL_LOGO")


class GoogleSettings(CommonSettings):
    CLIENT_ID: str = Field(default="client_id", validation_alias="GOOGLE_CLIENT_ID")
    CLIENT_SECRET: str = Field(default="client_secret", validation_alias="GOOGLE_CLIENT_SECRET")


class MQTTSettings(CommonSettings):
    HOSTNAME: str = Field(default="localhost", validation_alias="MQTT_HOSTNAME")
    PORT: int = Field(default=1883, validation_alias="MQTT_PORT")
    USERNAME: str = Field(default="admin", validation_alias="MQTT_USERNAME")
    PASSWORD: str = Field(default="Admin@123", validation_alias="MQTT_PASSWORD")


class KafkaSettings(CommonSettings):
    SERVER: str = Field(default="localhost:9092", validation_alias="KAFKA_SERVER")
    TOPIC: str = Field(default="train-job-topic", validation_alias="KAFKA_TOPIC")


class MapReduceSettings(CommonSettings):
    MODE: str = Field(default="local", validation_alias="MAPREDUCE_MODE")
    HEAD_ADDRESS: str = Field(default="localhost:7777", validation_alias="MAPREDUCE_HEAD_ADDRESS")
    WORKER_IDLE_TIMEOUT: int = Field(default=0, validation_alias="MAPREDUCE_WORKER_IDLE_TIMEOUT")
    ACTOR_IDLE_TIMEOUT: int = Field(default=0, validation_alias="MAPREDUCE_ACTOR_IDLE_TIMEOUT")


class BackendAddress(CommonSettings):
    HOST: str = Field(default="localhost", validation_alias="BACKEND_HOST")
    PORT: int = Field(default=9999, validation_alias="BACKEND_PORT")


class Settings(CommonSettings):
    """
    Centralized configuration management for project
    """
    # System Paths
    BASE_DIR: Path = BASE_DIR

    # Project Info
    PROJECT: ProjectInfo = Field(default_factory=ProjectInfo)

    # Address
    BACKEND: BackendAddress = Field(default_factory=BackendAddress)

    # Domain
    FRONTEND_URL: str = "http://localhost:3000"
    REDIRECT_URI: str = "http://localhost:9996"

    # Database Settings
    MONGODB: MongoDB = Field(default_factory=MongoDB)

    # Minio Settings
    MINIO: MinIOSettings = Field(default_factory=MinIOSettings)

    # Backblaze Storage Settings
    BACKBLAZE: BackblazeSettings = Field(default_factory=BackblazeSettings)

    # JWT Settings
    JWT: JWTSettings = Field(default_factory=JWTSettings)

    # Mail Settings
    MAIL: MailSettings = Field(default_factory=MailSettings)

    # Google Settings
    GOOGLE: GoogleSettings = Field(default_factory=GoogleSettings)

    # MQTT Settings
    MQTT: MQTTSettings = Field(default_factory=MQTTSettings)

    # Kafka Settings
    KAFKA: KafkaSettings = Field(default_factory=KafkaSettings)

    # PyMapReduce Settings
    PYMAPREDUCE: MapReduceSettings = Field(default_factory=MapReduceSettings)

    # List of allowed API sources
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",      # React/Next.js local
        "http://localhost:5173",      # Vite local
    ]


# Instantiate the settings object to be used across the application
settings = Settings()
