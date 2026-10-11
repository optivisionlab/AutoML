# Standard Libraries
import json
import aiomqtt
import logging

# Local Libraries
from src.config import settings


# Logging
logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self):
        self.hostname = settings.MQTT.HOSTNAME
        self.port = settings.MQTT.PORT
        self.username = settings.MQTT.USERNAME
        self.password = settings.MQTT.PASSWORD

        self.client = None
        self.is_connected = False

    async def connect(self):
        self.client = aiomqtt.Client(
            hostname=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password
        )

        try:
            await self.client.__aenter__()
            self.is_connected = True
            logger.info("Successfully connected to MQTT Broker")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT Broker. Reason: {e}")

    async def disconnect(self):
        if self.is_connected and self.client:
            await self.client.__aexit__(None, None, None)
            self.is_connected = False
            logger.info("Disconnected from MQTT Broker")

    async def publish(self, topic: str, payload: dict, qos: int = 1):
        if not self.is_connected or not self.client:
            logger.warning(f"MQTT Client is not connected. Dropping message for topic: {topic}")
            return

        try:
            await self.client.publish(topic, payload=json.dumps(payload), qos=qos)
        except Exception as e:
            logger.error(f"MQTT Publish Error on topic {topic}. Reason: {e}")


# Instantiate MQTT
mqtt_service = MQTTClient()
