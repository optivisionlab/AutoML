# Kafka consumer setup
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import yaml
import json
from database.get_dataset import job_update
import asyncio
import time

# Local Modules
from automl.v2.master import setup_job_tasks, JOB_TRACKER, reduce_results_for_job
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
    print("[Kafka Producer] Started")


async def stop_producer():
    global producer_instance
    if producer_instance:
        await producer_instance.stop()
        print("[Kafka Producer] Started")


def get_producer() -> AIOKafkaProducer:
    global producer_instance
    if producer_instance is None:
        raise RuntimeError("AIOKafkaProducer has not been started via lifespan")
    return producer_instance


async def handle_training_job(job_id: str, id_data: str, id_user: str, config: dict):
    """
    Xử lý một job từ Kafka
    """
    try:
        start = time.perf_counter()

        #  Đăng ký task vào hàng đợi
        await setup_job_tasks(job_id, id_data, id_user, config)

        # Chờ job hoàn thành
        tracker = JOB_TRACKER[job_id]
        await tracker["completion_event"].wait()
        start = time.perf_counter()

        # Job đã xong, thực hiện reduce
        final_result = reduce_results_for_job(job_id)
        end = time.perf_counter()

        version = 1
        await asyncio.to_thread(
            minIOStorage.uploaded_model,
            bucket_name="models",
            object_name=f"{id_user}/{job_id}/{final_result['best_model']}_{version}.pkl",
            model_bytes=final_result["model"]
        )

        await asyncio.to_thread(job_update.update_success, job_id, id_user, final_result)

        print(f"[Consumer Task] Completed job {job_id}: {end-start}")
        return {"job_id": job_id, "status": "success"}
        
    except Exception as e:
        # Lỗi từ quá trình huấn luyện
        error_msg = f"Training failure: {str(e)}"

        await asyncio.to_thread(job_update.update_failure, job_id, error_msg)
        raise Exception(error_msg)

    finally:
        # Dọn dẹp job
        if job_id in JOB_TRACKER:
            JOB_TRACKER.pop(job_id, None)


""" Hàm Consumer chạy tiến trình riêng """
async def kafka_consumer_process():
    consumer = None
    MAX_CONCURRENT_JOBS = 12

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

        while True:
            batch = await consumer.getmany(
                timeout_ms=3000, max_records=MAX_CONCURRENT_JOBS
            )

            if not batch:
                continue

            tasks = []
            messages_in_batch = []

            # VÒNG LẶP ĐỂ XỬ LÝ MESSAGE
            for tp, messages in batch.items():
                for msg in messages:
                    job_id = msg.key.decode('utf-8')
                    id_data = msg.value.get('id_data')
                    id_user = msg.value.get('id_user')
                    config = msg.value.get('config')

                    tasks.append(
                        asyncio.create_task(
                            handle_training_job(job_id, id_data, id_user, config)
                        )
                    )
                    messages_in_batch.append(msg)
        
            if not tasks:
                continue

            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = 0
            fail_count = 0
            for res in results:
                if isinstance(res, Exception):
                    fail_count += 1
                else:
                    success_count += 1
            print(f"[Consumer] Batch complete")

            offsets_to_commit = {}
            for tp, messages in batch.items():
                if messages:
                    last_message_in_partition = messages[-1]
                    offsets_to_commit[tp] = last_message_in_partition.offset + 1
            
            if offsets_to_commit:
                await consumer.commit(offsets_to_commit)

    except asyncio.CancelledError:
        print("[Consumer Task] Task was cancelled gracefully.")
        raise
    except Exception as e:
        print(f"[Consumer Task] Consumer error: {str(e)}")
    finally:
        if consumer:
            await consumer.stop()
        print(f"[Consumer Task] Consumer closed")
