# Standard Libraries
import time
from uuid import uuid4

# Third-party Libraries
from bson.objectid import ObjectId

# Local Modules
from database.get_dataset import get_database
from kafka_consumer import get_producer
from automl.v2.schemas import InputRequest, JobResponse


async def send_message(topic: str, key: str, message: dict):
    try:
        producer = get_producer()
    except RuntimeError:
        raise ConnectionError("Kafka Producer not initialized in the lifespan.")

    await producer.send_and_wait(
        topic=topic, 
        key=key.encode('utf-8'), 
        value=message
    )


def save_job_mongo(input: InputRequest, models_info) -> dict:
    db = get_database()
    user_collection = db["tbl_User"]
    job_collection = db["tbl_Job"]
    data_collection = db["tbl_Data"]


    try:
        # Tìm tên người dùng
        user_doc = user_collection.find_one({"_id": ObjectId(input.id_user)}, {"username": 1})

        if not user_doc:
            return {"status": "error", "message": "User not found"}
        user_name = user_doc.get("username")

        # Tìm tên dữ liệu
        data_doc = data_collection.find_one({"_id": ObjectId(input.id_data)}, {"dataName": 1})
        if not data_doc:
            return {"status": "error", "message": "Data not found"}
        data_name = data_doc.get("dataName")

        # Tạo một bản ghi job mới
        new_job = {
            "job_id": str(uuid4()),
            "best_model_id": models_info["best_model_id"],
            "best_model": models_info["best_model"],
            "model": models_info["model"],
            "best_params": models_info["best_params"],
            "best_score": models_info["best_score"],
            "orther_model_scores": models_info["model_scores"],
            "config": input.config,
            "data": {
                "id": input.id_data,
                "name": data_name
            },
            "user": {
                "id": input.id_user,
                "name": user_name
            },
            "status": 1,
            "activate": 0,
            "create_at": time.time()
        }

        # Chèn bản ghi job vào collection
        result = job_collection.insert_one(new_job)

        # Trả về kết quả
        return {
            "status": "success",
            "message": "Job saved successfully",
            "job_id": str(result.inserted_id)
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    

def save_job(input: InputRequest) -> str:
    db = get_database()
    user_collection = db["tbl_User"]
    job_collection = db["tbl_Job"]
    data_collection = db["tbl_Data"]
    
    # Tìm tên người dùng
    user_doc = user_collection.find_one({"_id": ObjectId(input.id_user)}, {"username": 1})

    if not user_doc:
        raise ValueError("User not found")
    user_name = user_doc.get("username")

    # Tìm tên dữ liệu
    data_doc = data_collection.find_one({"_id": ObjectId(input.id_data)}, {"dataName": 1})
    if not data_doc:
        raise ValueError("Data not found")
    data_name = data_doc.get("dataName")

    job_id = str(uuid4())

    # Tạo một bản ghi job mới
    new_job = {
        "job_id": job_id,
        "config": input.config,
        "data": {
            "id": input.id_data,
            "name": data_name
        },
        "user": {
            "id": input.id_user,
            "name": user_name
        },
        "status": 0,
        "activate": 0,
        "create_at": time.time()
    }

    msg_job = {
        "id_data": input.id_data,
        "config": input.config,
        "id_user": input.id_user
    }

    try:
        job_collection.insert_one(new_job)

    except Exception as e:
        raise Exception(f"{str(e)}");
    
    return job_id, msg_job


def convert_mongodb_document(doc: dict) -> dict:
    """Chuyển đổi ObjectId sang str"""
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def query_jobs(id_user: str, page: int, limit: int) -> tuple[list[dict], int]:
    db = get_database()
    job_collection = db["tbl_Job"]

    filter_query = {"user.id": id_user}
    
    # Đảm bảo trang và limit hợp lệ
    page = max(1, page)
    limit = max(1, limit)
    offset = (page - 1) * limit

    # Tính tổng số trang
    total_jobs = job_collection.count_documents(filter_query)
    total_pages = (total_jobs + limit - 1) // limit if total_jobs > 0 else 1
    
    # Nếu trang yêu cầu vượt quá tổng số trang, điều chỉnh offset về trang cuối cùng
    if page > total_pages and total_pages > 0:
         page = total_pages
         offset = (page - 1) * limit


    # Projection để lấy các trường cần thiết, tránh tải dữ liệu lớn
    projection_fields = {
        # Các trường loại bỏ
        "best_model": 0, "model": 0, "config": 0, "activate": 0 
    }

    jobs_cursor = (
        job_collection.find(filter_query, projection=projection_fields)
        .sort("create_at", -1)
        .skip(offset)
        .limit(limit)
    )

    # Chuyển _id thành str
    jobs_list_raw = [convert_mongodb_document(job) for job in jobs_cursor]

    return jobs_list_raw, total_pages, total_jobs


def get_model(id: str) -> dict:
    db = get_database()
    job_collection = db["tbl_Job"]

    model_doc = job_collection.find_one({"_id": ObjectId(id)}, {"model": 1})

    if not model_doc:
        raise ValueError("Data not found")
    
    model = model_doc.get("model", {})
    bucket_name = model.get("bucket_name")
    object_name = model.get("object_name")

    return bucket_name, object_name
