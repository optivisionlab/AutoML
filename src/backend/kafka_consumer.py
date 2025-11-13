# Kafka consumer setup
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition
from pymongo.asynchronous.database import AsyncDatabase
import os
import json
import asyncio
import io
import numpy as np
import joblib
from dotenv import load_dotenv

# Local Modules
from automl.v2.master import setup_job_tasks
from database.get_dataset import MongoDataLoader
from automl.v2.minio import minIOStorage
from automl.v2.master import get_config_hash


# Load file .env
load_dotenv()


# =======================================================
# KHAI BÁO BIÉN PRODUCER
producer_instance: AIOKafkaProducer | None = None

async def start_producer():
    global producer_instance
    producer_instance = AIOKafkaProducer(
        bootstrap_servers=os.getenv('KAFKA_SERVER', 'localhost:9092'),
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    await producer_instance.start()
    print("[Kafka Producer] Started")


async def stop_producer():
    global producer_instance
    if producer_instance:
        await producer_instance.stop()
        print("[Kafka Producer] Stopped")


def get_producer() -> AIOKafkaProducer:
    global producer_instance
    if producer_instance is None:
        raise RuntimeError("AIOKafkaProducer has not been started via lifespan")
    return producer_instance


async def handle_training_job(job_id: str, id_data: str, id_user: str, config: dict, db: AsyncDatabase):
    dataset = MongoDataLoader(db)
    try:
        # Thực hiện cache dataset (tiền xử lý ở master thay vì để mỗi worker phải thực hiện việc này -> tốn tài nguyên)
        # Sử dụng 2 định dạng:
        """
        parquet - cho việc lưu trữ lâu dài (tốn ít tài nguyên)
        feather - cho việc đọc ghi (tối ưu hóa về tốc độ)
        """
        cache_bucket = "cache"
        models_bucket = "models"
        list_feature = config.get("list_feature")
        target = config.get("target")

        config_hash = get_config_hash(id_data, list_feature, target)
        data_cache_path = f"{id_data}/{config_hash}.npz"
        preprocessor_cache_path = f"{id_data}/{config_hash}_preprocessor.joblib"
        le_target_cache_path = f"{id_data}/{config_hash}_le_target.joblib"

        cache_exists = await asyncio.to_thread(
            minIOStorage.check_object_exists,
            cache_bucket,
            data_cache_path
        )

        if not cache_exists:
            X_processed, y_processed, preprocessor, le_target = await dataset.get_processed_data(
                id_data, 
                list_feature,
                target
            )

            with io.BytesIO() as f_data, io.BytesIO() as f_pre, io.BytesIO() as f_target:
                # Chạy cả 3 tác vụ nén/dump song song trên các thread
                await asyncio.gather(
                    asyncio.to_thread(np.savez_compressed, f_data, X=X_processed, y=y_processed),
                    asyncio.to_thread(joblib.dump, preprocessor, f_pre),
                    asyncio.to_thread(joblib.dump, le_target, f_target)
                )

                f_data.seek(0); f_pre.seek(0); f_target.seek(0)

                # Tải 3 file lên song song
                await asyncio.gather(
                    asyncio.to_thread(minIOStorage.uploaded_object, cache_bucket, data_cache_path, f_data.read()),
                    asyncio.to_thread(minIOStorage.uploaded_object, cache_bucket, preprocessor_cache_path, f_pre.read()),
                    asyncio.to_thread(minIOStorage.uploaded_object, cache_bucket, le_target_cache_path, f_target.read())
                )

        preprocessor_job_path = f"{id_user}/{job_id}/preprocessor.joblib"
        target_job_path = f"{id_user}/{job_id}/target.joblib"

        await asyncio.gather(
            asyncio.to_thread(
                minIOStorage.copy_object,
                source_bucket=cache_bucket,
                source_key=preprocessor_cache_path,
                dest_bucket=models_bucket,
                dest_key=preprocessor_job_path
            ),
            asyncio.to_thread(
                minIOStorage.copy_object,
                source_bucket=cache_bucket,
                source_key=le_target_cache_path,
                dest_bucket=models_bucket,
                dest_key=target_job_path
            )
        )
            
        # Đăng ký task vào hàng đợi
        await setup_job_tasks(job_id, id_data, id_user, config)
        print(f"[Consumer] Successfully submitted job {job_id} to Master")
        
    except Exception as e:
        print(f"[Consumer] Failed to handle job {job_id}: {e}")
        raise e



""" Hàm Consumer chạy tiến trình riêng """
async def kafka_consumer_process(db: AsyncDatabase):
    consumer = None

    MAX_CONCURRENT_HANDLERS = 1
    sem = asyncio.Semaphore(MAX_CONCURRENT_HANDLERS)

    async def process_message_safely(msg):
        """
        Wrapper để xử lý message và commit thành công
        """
        job_id = msg.key.decode('utf-8')
        tp = TopicPartition(msg.topic, msg.partition)

        try:
            async with sem:
                id_data = msg.value.get('id_data')
                id_user = msg.value.get('id_user')
                config = msg.value.get('config')

                await handle_training_job(job_id, id_data, id_user, config, db)
            
            # Xử lý thành công -> commit offset
            await consumer.commit({tp: msg.offset + 1})
            print(f"[Consumer] Committed offset for job {job_id}")
        
        except Exception as e:
            print(f"[Consumer] ERROR processing job {job_id}")
            # dlq_producer = get_producer()

            # # Gửi message lỗi sang một topic khác 
            # dlq_message = {
            #     "original_message": msg.value,
            #     "error_time": time.time(),
            #     "error_details": str(e)
            # }
            # await dlq_producer.send_and_wait("train-job-dlq", dlq_message)
            await consumer.commit({tp: msg.offset + 1})

    try:
        # KHỞI TẠO VÀ START CONSUMER 
        consumer = AIOKafkaConsumer(
            os.getenv('KAFKA_TOPIC', 'example-topic'),
            bootstrap_servers=os.getenv('KAFKA_SERVER', 'localhost:9092'),
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            group_id='train-consumer-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        await consumer.start()
        print(f"[Consumer Task] Kafka is running...")

        # Xử lý message bằng vòng lặp 'async for'
        async for msg in consumer:
            asyncio.create_task(process_message_safely(msg))
    
    except asyncio.CancelledError:
        print("[Consumer Task] Task was cancelled gracefully.")
        raise
    except Exception as e:
        print(f"[Consumer Task] Exception occurred: {str(e)}")
    finally:
        if consumer:
            await consumer.stop()
        print("[Consumer Task] Consumer closed")
