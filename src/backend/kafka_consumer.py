# Kafka consumer setup
import json
from kafka import KafkaConsumer
from automl.engine import train_json_from_job
consumer = KafkaConsumer(
    "train-job-topic",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    group_id="train-consumer-group",
    auto_offset_reset="earliest",
    enable_auto_commit=True
)

def run_train_consumer():
    print("Kafka consumer is running...")

    for msg in consumer:
        try:
            job = msg.value
            print(f"[Kafka] Received job: {job['job_id']}")
            train_json_from_job(job)
            print(f"[Kafka] Completed and saved job {job['job_id']} to MongoDB")

        except Exception as e:
            print(f"[Kafka] Error processing job: {e}")

if __name__ == "__main__":
    run_train_consumer()
    pass
