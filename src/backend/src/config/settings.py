# Standard Libraries
from pathlib import Path

# Third-party Libraries
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MinIOSettings(BaseModel):
    ENDPOINT: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    ACCESS_KEY: str = Field(default="admin", validation_alias="MINIO_ACCESS_KEY")
    SECRET_KEY: str = Field(default="password123", validation_alias="MINIO_SECRET_KEY")


class MongoDB(BaseModel):
    CONNECT: str = Field(default="localhost:27017", validation_alias="MONGODB_CONNECT")
    NAME: str = "AutoML"

class ProjectInfo(BaseModel):
    NAME: str = "HAutoML"
    VERSION: str = "0.3.0"
    ENVIRONMENT: str = "development"


class JWTSettings(BaseModel):
    SECRET_KEY: str = Field(default="secret-key", validation_alias="SECRET_KEY")
    ALGORITHM: str = Field(default="HS256", validation_alias="ALGORITHM")
    ACCESS_EXPIRE: int = Field(default=15, validation_alias="ACCESS_EXPIRE")
    REFRESH_EXPIRE: int = Field(default=7, validation_alias="REFRESH_EXPIRE")


class MailSettings(BaseModel):
    USERNAME: str = Field(default="username", validation_alias="MAIL_USERNAME")
    PASSWORD: str = Field(default="password", validation_alias="MAIL_PASSWORD")


class GoogleSettings(BaseModel):
    CLIENT_ID: str = Field(default="client_id", validation_alias="GOOGLE_CLIENT_ID")
    CLIENT_SECRET: str = Field(default="client_secret", validation_alias="GOOGLE_CLIENT_SECRET")


class MQTTSettings(BaseModel):
    HOSTNAME: str = Field(default="localhost", validation_alias="MQTT_HOSTNAME")
    PORT: int = Field(default=1883, validation_alias="MQTT_PORT")
    USERNAME: str = Field(default="admin", validation_alias="MQTT_USERNAME")
    PASSWORD: str = Field(default="Admin@123", validation_alias="MQTT_PASSWORD")


class KafkaSettings(BaseModel):
    SERVER: str = Field(default="localhost:9092", validation_alias="KAFKA_SERVER")
    TOPIC: str = Field(default="train-job-topic", validation_alias="KAFKA_TOPIC")


class MapReduceMode(str):
    LOCAL = "local"
    CLUSTER = "cluster"


class MapReduceSettings(BaseModel):
    MODE: str = Field(default=MapReduceMode.CLUSTER, validation_alias="MAPREDUCE_MODE")
    HEAD_ADDRESS: str = Field(default="10.100.200.119:7777", validation_alias="MAPREDUCE_HEAD_ADDRESS")


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

    # PyMapReduce Settings
    PYMAPREDUCE: MapReduceSettings = MapReduceSettings()

    # List of allowed API sources
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",      # React/Next.js local
        "http://localhost:5173",      # Vite local
    ]

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Instantiate the settings object to be used across the application
settings = Settings()
