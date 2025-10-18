# Kafka consumer setup
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
import yaml
import json
from database.get_dataset import get_database
import asyncio
import os

# Local Modules
from automl.v2.master import JobManager, ACTIVE_JOBS
from automl.v2.minio import minIOStorage

file_path = ".config.yml"
with open(file_path, "r") as f:
    data = yaml.safe_load(f)

# =======================================================
# KHAI BÁO BIÉN PRODUCER
producer_instance: AIOKafkaProducer | None = None

async def start_producer():
    global producer_instance
    producer_instance = AIOKafkaProducer(
        bootstrap_servers=data['KAFKA_SERVER'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    await producer_instance.start()
    print("[Kafka Producer] Started.")


async def stop_producer():
    global producer_instance
    if producer_instance:
        await producer_instance.stop()
        print("[Kafka Producer] Started.")


def get_producer() -> AIOKafkaProducer:
    global producer_instance
    if producer_instance is None:
        raise RuntimeError("AIOKafkaProducer has not been started via lifespan")
    return producer_instance



async def handle_training_job(job_id, id_data, id_user, config, tp, offset, consumer):
    master_server_url = f"http://{data['HOST_BACK_END']}:{data['PORT_BACK_END']}" 
    manager = JobManager(job_id, id_data, id_user, config, master_server_url) 
    ACTIVE_JOBS[job_id] = manager

    try:
        import time
        start = time.time()

        # Chạy toàn bộ quá trình điều phối và chờ kết quả
        final_result = await manager.run()

        version = 1

        await asyncio.to_thread(
            minIOStorage.uploaded_model,
            bucket_name="models",
            object_name=f"{id_user}/{job_id}/{final_result['best_model']}_{version}.pkl",
            model_bytes=final_result["model"]
        )

        def update_success():
            db = get_database()
            job_collection = db["tbl_Job"]
            update_data = {
                "$set": {
                    "best_model_id": final_result["best_model_id"],
                    "best_model": final_result["best_model"],
                    "model": {
                        "bucket_name": "models",
                        "object_name": f"{id_user}/{job_id}/{final_result['best_model']}_{version}.pkl"
                    },
                    "best_params": final_result["best_params"],
                    "best_score": final_result["best_score"],
                    "orther_model_scores": final_result["model_scores"],
                    "status": 1
                }
            }
            job_collection.update_one({"job_id": job_id}, update_data)

        await asyncio.to_thread(update_success)
        end = time.time()
        print(f"[Consumer Task] Completed job {job_id}: {end-start}")

        await consumer.commit({
            tp: offset + 1
        })
        print(f"[Consumer Task] Committed offset {offset + 1} after processing")

    except Exception as e:
        # Lỗi từ quá trình huấn luyện
        error_msg = f"Training failure: {str(e)}"
        print(f"[JOB {job_id}] {error_msg}")

    finally:
        # Dọn dẹp job
        if job_id in ACTIVE_JOBS:
            del ACTIVE_JOBS[job_id]


""" Hàm Consumer chạy tiến trình riêng """
async def kafka_consumer_process():
    consumer = None

    try:
        # KHỞI TẠO VÀ START CONSUMER 
        consumer = AIOKafkaConsumer(
            data['KAFKA_TOPIC'],
            bootstrap_servers=data['KAFKA_SERVER'],
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            group_id='train-consumer-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        await consumer.start()
        print(f"[Consumer Task] Kafka is running...")

        # VÒNG LẶP ĐỂ XỬ LÝ MESSAGE 
        async for message in consumer:
            job_id = message.key.decode('utf-8')
            id_data = message.value.get('id_data')
            id_user = message.value.get('id_user')
            config = message.value.get('config')

            tp = TopicPartition(message.topic, message.partition)

            asyncio.create_task(
                handle_training_job(
                    job_id, id_data, id_user, config, tp, message.offset, consumer
                )
            )
    except asyncio.CancelledError:
        print("[Consumer Task] Task was cancelled gracefully.")
        raise
    except Exception as e:
        print(f"[Consumer Task] Consumer error: {str(e)}")
    finally:
        if consumer:
            await consumer.stop()
        print(f"[Consumer Task] Consumer closed")
