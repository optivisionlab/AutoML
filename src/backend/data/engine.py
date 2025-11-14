from bson.objectid import ObjectId
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

import base64
import pandas as pd
import io
import time

from automl.v2.minio import minIOStorage


# Hàm lấy danh sách data
async def get_all_data(db: AsyncDatabase):
    data_collection = db.tbl_Data
    filter_query = {"activate": 1} # activate = 1 <=> kích hoạt dataset

    data = await data_collection.find(filter_query, {"username": 0, "role": 0})
    list_data = []
    for item in data:
        item["_id"] = str(item["_id"])
        list_data.append(item)
    return list_data


# Hàm lấy danh sách data
async def get_list_data(id_user, db: AsyncDatabase):
    data_collection = db.tbl_Data
    filter_query = {"userId": id_user, "activate": 1} # activate = 1 <=> kích hoạt dataset

    data = await data_collection.find(filter_query, {"username": 0, "role": 0})
    list_data = []
    for item in data:
        item["_id"] = str(item["_id"])
        list_data.append(item)
    return list_data

# Hàm lấy 1 data
async def get_one_data(id_data: str, db: AsyncDatabase):
    data_collection = db.tbl_Data
    try:
        data = await data_collection.find_one({"_id": ObjectId(id_data)})
        if not data:
            raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu với ID đã cho.")
        return JSONResponse(content=serialize_mongo_doc(data))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi truy vấn dữ liệu: {str(e)}")


def encode_csv_to_base64(file_path):
    contents = file_path.file.read()
    encoded_data = base64.b64encode(contents).decode("utf-8")
    return encoded_data


def serialize_mongo_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

async def upload_data_to_minio(file_data, dataName: str, dataType, userId, db: AsyncDatabase):
    now = time.time()
    user_collection = db.tbl_User
    data_collection = db.tbl_Data

    try:
        # Lấy thông tin người dùng từ userId
        user = await user_collection.find_one({"_id": ObjectId(userId)})
        if not user:
            raise Exception(f"Not found user")

        file_content_bytes = file_data.file.read()
        csv_stream = io.BytesIO(file_content_bytes)
        df = pd.read_csv(csv_stream)

        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False)
        parquet_buffer.seek(0)

        data_name_copy = dataName.strip().replace(' ', '_').lower()

        username = user.get("username")
        role = user.get("role")
        
        # Nếu là admin thì đặt userId = 0
        if role == "admin":
            userId = "0"

        minIOStorage.uploaded_dataset(
            bucket_name="dataset",
            object_name=f"{userId}/{data_name_copy}.parquet",
            parquet_buffer=parquet_buffer
        )

        data_to_insert = {
            "dataName": dataName,
            "dataType": dataType,
            "data_link": {
                "bucket_name": "dataset",
                "object_name": f"{userId}/{data_name_copy}.parquet"
            },
            "latestUpdate": now,
            "createDate": now,
            "userId": userId,
            "username": username,
            "role": role,
            "activate": 1 # activate = 1 --- kích hoạt dataset
        }

        result = await data_collection.insert_one(data_to_insert)
        if result.inserted_id:
            serialize_mongo_doc(data_to_insert)
            return data_to_insert
        else:
            raise Exception(f"Error when insert data to mongo")
    except Exception as e:
        raise Exception(f"Error when upload dataset: {str(e)}")


async def update_dataset_to_minio_by_id(dataset_id: str, db: AsyncDatabase, dataName: str = None, dataType: str = None, file_data=None):
    data_collection = db.tbl_Data
    try:

        # Lấy bản ghi hiện tại để so sánh
        current_data = await data_collection.find_one({"_id": ObjectId(dataset_id)})
        if not current_data:
            raise Exception(f"Not found dataset")

        update_fields = {}
        data_changed = False

        # Kiểm tra từng trường và chỉ thêm vào nếu có thay đổi
        if dataName and dataName != current_data.get("dataName"):
            update_fields["dataName"] = dataName
            data_changed = True
        if dataType and dataType != current_data.get("dataType"):
            update_fields["dataType"] = dataType
            data_changed = True

        data_link = current_data.get("data_link", {})
        bucket_name = data_link.get("bucket_name")
        object_name = data_link.get("object_name")

        if file_data:
            # Read file and change to DataFrame
            file_content_bytes = file_data.file.read()
            csv_stream = io.BytesIO(file_content_bytes)
            df = pd.read_csv(csv_stream)

            # Get dataset from MinIO
            try:
                with minIOStorage.get_object(bucket_name, object_name) as parquet_stream:
                    df_retrieved = pd.read_parquet(parquet_stream)
            except Exception as e:
                # Xử lý trường hợp không tìm thấy file cũ (NoSuchKey)
                df_retrieved = None

            if df_retrieved is not None and not df.equals(df_retrieved):
                parquet_buffer = io.BytesIO()
                df.to_parquet(parquet_buffer, index=False)
                parquet_buffer.seek(0)

                minIOStorage.uploaded_dataset(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    parquet_buffer=parquet_buffer
                )
                data_changed = True

        if data_changed:
            update_fields["latestUpdate"] = time.time()
            await data_collection.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$set": update_fields}
            )
            
        return data_changed

    except Exception as e:
        raise Exception(f"Error: {str(e)}")


async def delete_dataset_at_minio_by_id(dataset_id: str, db: AsyncDatabase):
    data_collection = db.tbl_Data
    dataset = await data_collection.find_one({"_id": ObjectId(dataset_id)}, {"data_link": 1})
    if not dataset:
        raise Exception(f"Not found dataset")
    
    data_link = dataset.get("data_link", {})
    bucket_name = data_link.get("bucket_name")
    object_name = data_link.get("object_name")

    if not (bucket_name and object_name):
        data_collection.delete_one({{"_id": ObjectId(dataset_id)}})
        return True
    
    try:
        dataset_minio_success = minIOStorage.remove_object(
            bucket_name=bucket_name,
            object_name=object_name
        )
        
        if dataset_minio_success:
            dataset_mongo_result = await data_collection.delete_one({"_id": ObjectId(dataset_id)})
            
            if dataset_mongo_result.deleted_count == 1:
                return True
            else:
                raise Exception("Removed MinIO file, but error when removing MongoDB metadata")
        else:
            raise Exception("Remove MinIO file failure")

    except Exception as e:
        raise Exception(f"Error when removing: {str(e)}")

