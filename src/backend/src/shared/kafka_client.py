# Standard Libraries
import asyncio
import json
import logging
from typing import Any
from collections.abc import AsyncGenerator, Callable

# Third-party Libraries
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import KafkaError

# Local Libraries
from src.config.settings import settings


# Logging
logger = logging.getLogger(__name__)


class KafkaClient:
    """
    Asynchronous Kafka client supporting producer, consumer, and topic management
    """
    def __init__(
        self,
        bootstrap_servers: str | None = None,
        default_topic: str | None = None,
    ):
        self.bootstrap_servers: str = bootstrap_servers or settings.KAFKA.SERVER
        self.default_topic: str = default_topic or settings.KAFKA.TOPIC

        self.producer: AIOKafkaProducer | None = None
        self.is_connected: bool = False
        self._consumer_tasks: list[asyncio.Task] = []

    # Serializers & Deserializers
    @staticmethod
    def _serialize_value(value: Any) -> bytes:
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, (dict, list, int, float, bool)):
            return json.dumps(value, ensure_ascii=False).encode("utf-8")
        return str(value).encode("utf-8")

    @staticmethod
    def _serialize_key(key: str | bytes | None) -> bytes | None:
        if key is None:
            return None
        if isinstance(key, bytes):
            return key
        if isinstance(key, str):
            return key.encode("utf-8")
        return str(key).encode("utf-8")

    @staticmethod
    def _deserialize_value(value: bytes | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return value

    # Connection Management
    async def connect(self) -> None:
        """
        Initialize and start the Kafka producer.
        """
        if self.is_connected and self.producer:
            logger.info("Kafka Producer is already connected.")
            return

        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=self._serialize_value,
            key_serializer=self._serialize_key,
        )

        try:
            await self.producer.start()
            self.is_connected = True
            logger.info(f"Successfully connected to Kafka Broker at {self.bootstrap_servers}")
        except Exception as e:
            self.is_connected = False
            self.producer = None
            logger.error(f"Failed to connect to Kafka Broker at {self.bootstrap_servers}. Reason: {e}")

    async def disconnect(self) -> None:
        """
        Gracefully stop the Kafka producer and any running consumer tasks.
        """
        # Cancel any active listener tasks
        for task in self._consumer_tasks:
            if not task.done():
                task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks, return_exceptions=True)
            self._consumer_tasks.clear()

        if self.is_connected and self.producer:
            try:
                await self.producer.stop()
                logger.info("Disconnected from Kafka Broker")
            except Exception as e:
                logger.error(f"Error disconnecting Kafka Producer: {e}")
            finally:
                self.is_connected = False
                self.producer = None

    # Producer Methods
    async def send_message(
        self,
        topic: str | None = None,
        value: Any = None,
        key: str | bytes | None = None,
        headers: list[tuple] | None = None,
        partition: int | None = None,
    ) -> Any | None:
        """
        Send a message to a Kafka topic and wait for acknowledgment.
        """
        target_topic = topic or self.default_topic
        if not target_topic:
            logger.error("Kafka send_message failed: No topic specified and no default topic configured.")
            return None

        if not self.is_connected or not self.producer:
            logger.warning(f"Kafka Producer is not connected. Attempting to connect to {self.bootstrap_servers}...")
            await self.connect()
            if not self.is_connected or not self.producer:
                logger.error(f"Kafka Producer is unavailable. Dropping message for topic: {target_topic}")
                return None

        try:
            record_metadata = await self.producer.send_and_wait(
                topic=target_topic,
                value=value,
                key=key,
                headers=headers,
                partition=partition,
            )
            logger.info(
                f"Kafka message delivered to topic '{record_metadata.topic}' "
                f"[partition {record_metadata.partition}] at offset {record_metadata.offset}"
            )
            return record_metadata
        except KafkaError as e:
            logger.error(f"Kafka send_message error on topic '{target_topic}'. Reason: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending Kafka message to topic '{target_topic}': {e}")
            return None

    # Consumer Factory & Consumer Generator
    def create_consumer(
        self,
        *topics: str,
        group_id: str | None = None,
        auto_offset_reset: str = "earliest",
        enable_auto_commit: bool = True,
        **kwargs,
    ) -> AIOKafkaConsumer:
        """
        Factory to create a configured instance.
        """
        target_topics = topics if topics else (self.default_topic,)
        return AIOKafkaConsumer(
            *target_topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=enable_auto_commit,
            value_deserializer=self._deserialize_value,
            **kwargs,
        )

    async def consume_messages(
        self,
        *topics: str,
        group_id: str | None = None,
        auto_offset_reset: str = "earliest",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Async generator that consumes messages from specified topics.
        """
        target_topics = topics if topics else (self.default_topic,)
        consumer = self.create_consumer(
            *target_topics,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
        )

        try:
            await consumer.start()
            logger.info(f"Kafka Consumer started for topics: {target_topics}, group_id: {group_id}")
            async for msg in consumer:
                yield {
                    "topic": msg.topic,
                    "partition": msg.partition,
                    "offset": msg.offset,
                    "key": msg.key.decode("utf-8") if isinstance(msg.key, bytes) else msg.key,
                    "value": msg.value,
                    "timestamp": msg.timestamp,
                    "headers": msg.headers,
                }
        except asyncio.CancelledError:
            logger.info(f"Kafka Consumer cancelled for topics: {target_topics}")
        except Exception as e:
            logger.error(f"Kafka Consumer error for topics {target_topics}: {e}")
        finally:
            await consumer.stop()
            logger.info(f"Kafka Consumer stopped for topics: {target_topics}")

    def start_listener(
        self,
        topic: str,
        group_id: str,
        callback: Callable[[dict[str, Any]], Any],
        auto_offset_reset: str = "earliest",
    ) -> asyncio.Task:
        """
        Start an asynchronous background task that listens to a topic and invokes callback(msg).
        """
        async def _listen_loop():
            async for msg in self.consume_messages(topic, group_id=group_id, auto_offset_reset=auto_offset_reset):
                try:
                    res = callback(msg)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as ex:
                    logger.error(f"Error processing Kafka message from topic '{topic}': {ex}")

        task = asyncio.create_task(_listen_loop())
        self._consumer_tasks.append(task)
        return task

    # Topic & Admin Management
    async def create_topics(
        self,
        topic_names: list[str],
        num_partitions: int = 1,
        replication_factor: int = 1,
    ) -> bool:
        """
        Create one or more Kafka topics if they do not exist.
        """
        admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        try:
            await admin.start()
            new_topics = [
                NewTopic(
                    name=name,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor,
                )
                for name in topic_names
            ]
            await admin.create_topics(new_topics)
            logger.info(f"Successfully created Kafka topics: {topic_names}")
            return True
        except Exception as e:
            logger.warning(f"Failed or skipped creating Kafka topics {topic_names}. Reason: {e}")
            return False
        finally:
            await admin.close()

    async def list_topics(self) -> list[str]:
        """
        List all available Kafka topics.
        """
        admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        try:
            await admin.start()
            metadata = await admin.describe_cluster()
            topics = metadata.get("topics", [])
            return [t.get("topic") if isinstance(t, dict) else str(t) for t in topics]
        except Exception as e:
            logger.error(f"Failed to list Kafka topics: {e}")
            return []
        finally:
            await admin.close()

    async def ping(self) -> bool:
        """
        Check if the Kafka broker is reachable.
        """
        admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        try:
            await admin.start()
            cluster_metadata = await admin.describe_cluster()
            return bool(cluster_metadata and "brokers" in cluster_metadata)
        except Exception as e:
            logger.debug(f"Kafka ping failed: {e}")
            return False
        finally:
            try:
                await admin.close()
            except Exception:
                pass


# Instantiate Kafka Singleton
kafka_service = KafkaClient()
