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
    active_training_jobs: dict[str, asyncio.Task] = {}
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

        async for message in kafka_service.consume_messages(topic, group_id="automl_trainers"):
            try:
                job_id = message.get("key")
                payload = message.get("value") or {}

                if not job_id or not isinstance(payload, dict):
                    logger.warning(f"Received malformed Kafka message on topic '{topic}': {message}")
                    continue

                # Handle cancellation request
                if payload.get("action") == "cancel":
                    logger.info(f"Received cancellation command for Training Job: ID={job_id}")
                    running_job_task = active_training_jobs.get(str(job_id))
                    if running_job_task and not running_job_task.done():
                        running_job_task.cancel()
                        logger.info(f"Successfully triggered cancellation for Job Task {job_id}")
                    continue

                dataset_id = payload.get("dataset_id")
                user_id = payload.get("user_id")
                config = payload.get("config") or {}

                logger.info(f"Received Kafka Training Job: ID={job_id}, Dataset={dataset_id}, User={user_id}")

                # Run job asynchronously and track active job task
                current_job_id = str(job_id)
                job_task = asyncio.create_task(
                    training_service.process_training_job(
                        job_id=job_id,
                        dataset_id=dataset_id,
                        user_id=user_id,
                        config=config
                    )
                )

                # Keep track of active job for potential cancellation
                active_training_jobs[current_job_id] = job_task

                # Clean up finished job from dictionary to avoid memory leak
                def cleanup_job(_completed_task: asyncio.Task, target_id: str = current_job_id) -> None:
                    active_training_jobs.pop(target_id, None)

                job_task.add_done_callback(cleanup_job)

            except Exception as exc:
                logger.error(f"Error processing Kafka message: {exc}", exc_info=True)

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
