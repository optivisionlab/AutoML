# Standard Libraries
import asyncio
import logging

# Local Libraries
from src.config import setup_logging, settings, databases
from src.shared import kafka_service, minio_service, MapReduceManager
from src.modules.trainings import TrainingRepository, TrainingService
from src.modules.notifications import NotificationRepository, NotificationService


# Activate Logging
if not logging.getLogger().handlers:
    setup_logging()

logger = logging.getLogger("training_consumer")


async def start_training_consumer() -> None:
    """
    Kafka Consumer Worker that continuously listens to training jobs from Kafka topic
    """
    active_tasks: set[asyncio.Task] = set()
    try:
        logger.info("Initializing Training Consumer resources...")
        await databases.DatabaseManager.connection()
        await MapReduceManager.get_driver()

        # Instantiate Repositories and Services
        db = databases.DatabaseManager.db
        training_repo = TrainingRepository(db)
        notif_repo = NotificationRepository(db)
        notif_service = NotificationService(notif_repo)
        training_service = TrainingService(repo=training_repo, notif_service=notif_service)

        # Start Kafka Listener
        topic = settings.KAFKA.TOPIC
        logger.info(f"Training Consumer ready. Listening on Kafka topic: '{topic}'...")

        async for msg in kafka_service.consume_messages(topic, group_id="automl_trainers"):
            try:
                job_id = msg.get("key")
                payload = msg.get("value") or {}

                if not job_id or not isinstance(payload, dict):
                    logger.warning(f"Received malformed Kafka message on topic '{topic}': {msg}")
                    continue

                dataset_id = payload.get("dataset_id")
                user_id = payload.get("user_id")
                config = payload.get("config") or {}

                logger.info(f"Received Kafka Training Job: ID={job_id}, Dataset={dataset_id}, User={user_id}")

                # Run job asynchronously and track task
                task = asyncio.create_task(
                    training_service.process_training_job(
                        job_id=job_id,
                        dataset_id=dataset_id,
                        user_id=user_id,
                        config=config
                    )
                )
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

            except Exception as e:
                logger.error(f"Error processing Kafka message: {e}", exc_info=True)

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received. Stopping Training Consumer gracefully...")
    finally:
        logger.info("Cleaning up connections and resources...")
        try:
            await kafka_service.disconnect()
        except Exception as e:
            logger.debug(f"Error disconnecting Kafka: {e}")

        try:
            await MapReduceManager.shutdown()
        except Exception as e:
            logger.debug(f"Error shutting down MapReduce: {e}")

        try:
            await minio_service.close()
        except Exception as e:
            logger.debug(f"Error closing MinIO session: {e}")

        try:
            await databases.DatabaseManager.close_connection()
        except Exception as e:
            logger.debug(f"Error closing DB connection: {e}")

        logger.info("Training Consumer shut down successfully.")


def main():
    try:
        asyncio.run(start_training_consumer())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
