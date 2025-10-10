from pydantic import BaseModel
from typing import List
from database.database import get_database
from bson.objectid import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
from automl.v2.minio import minIOStorage

import base64
import pandas as pd
import io
import time

db = get_database()
data_collection = db["tbl_Data"]
user_collection = db["tbl_User"]

# Hàm lấy danh sách data
def get_list_data(id_user):
    data = data_collection.find({"userId": id_user})
    list_data = []
    for item in data:
        item["_id"] = str(item["_id"])
        list_data.append(item)
    return list_data

# Hàm lấy 1 data
def get_one_data(id_data: str):
    try:
        data = data_collection.find_one({"_id": ObjectId(id_data)})
        if not data:
            raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu với ID đã cho.")
        return JSONResponse(content=serialize_mongo_doc(data))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi truy vấn dữ liệu: {str(e)}")

def get_data_base64(id_data):
    try:
        object_id = ObjectId(id_data)
        data = data_collection.find_one({"_id": object_id})

        if data and "dataFile" in data:
            return data["dataFile"]
        else:
            return None

    except Exception as e:
        print(f"Đã xảy ra lỗi khi truy vấn MongoDB: {e}")
        return None


def encode_csv_to_base64(file_path):
    contents = file_path.file.read()
    encoded_data = base64.b64encode(contents).decode("utf-8")
    return encoded_data


def decode_base64_to_dataframe(id_data):
    base64_string = get_data_base64(id_data=id_data)
    # Giai ma Base64 thanh du lieu nhi phan
    decoded_bytes = base64.b64decode(base64_string)

    # Chuyen du lieu nhi phan thanh doi tuong giong file (stringIO)
    decoded_buffer = io.StringIO(decoded_bytes.decode("utf-8"))

    # Doc du lieu vao DataFrame
    df = pd.read_csv(decoded_buffer)

    return df


def get_data_from_mongodb_by_id(id_data):
    df = decode_base64_to_dataframe(id_data=id_data)
    class_names = df.iloc[:, -1].unique().tolist()
    return df, class_names


def serialize_mongo_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc


def upload_data(file_data, dataName, dataType, userId):
    now = time.time()
    encoded_file = encode_csv_to_base64(file_data)

    # Lấy thông tin người dùng từ userId
    user = user_collection.find_one({"_id": ObjectId(userId)})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    username = user.get("username")
    role = user.get("role")

    # Nếu là admin thì đặt userId = 0
    if role == "admin":
        userId = "0"

    data_to_insert = {
        "dataName": dataName,
        "dataType": dataType,
        "dataFile": encoded_file,
        "latestUpdate": now,
        "createDate": now,
        "list_feature": [],
        "target": None,
        "userId": userId,
        "username": username,
        "role": role,
    }

    result = data_collection.insert_one(data_to_insert)
    if result.inserted_id:
        serialize_mongo_doc(data_to_insert)
        return JSONResponse(content=data_to_insert)
    else:
        raise HTTPException(status_code=500, detail="Đã xảy ra lỗi thêm bộ dữ liệu")


def upload_data_to_minio(file_data, dataName: str, dataType, userId):
    now = time.time()

    try:
        # Lấy thông tin người dùng từ userId
        user = user_collection.find_one({"_id": ObjectId(userId)})
        if not user:
            raise Exception(f"Not found user")

        file_content_bytes = file_data.file.read()
        csv_stream = io.BytesIO(file_content_bytes)
        df = pd.read_csv(csv_stream)

        parquet_buffer = io.BytesIO()
        df.to_parquet(parquet_buffer, index=False)
        parquet_buffer.seek(0)

        data_name_copy = dataName.strip().replace(' ', '_')
        from uuid import uuid4
        data_id = str(uuid4())

        minIOStorage.uploaded_dataset(
            bucket_name=f"dataset",
            object_name=f"{userId}/{data_id}/{data_name_copy}.parquet",
            parquet_buffer=parquet_buffer
        )

        username = user.get("username")
        role = user.get("role")

        # Nếu là admin thì đặt userId = 0
        if role == "admin":
            userId = "0"

        data_to_insert = {
            "_id": data_id,
            "dataName": dataName,
            "dataType": dataType,
            "data_link": {
                "bucket_name": f"{userId}",
                "object_name": f"dataset/{dataName}.parquet"
            },
            "latestUpdate": now,
            "createDate": now,
            "user": {
                "id": userId,
                "name": username
            },
            "role": role,
        }

        result = data_collection.insert_one(data_to_insert)
        if result.inserted_id:
            serialize_mongo_doc(data_to_insert)
            return data_to_insert
        else:
            raise Exception(f"Error when insert data to mongo")
    except Exception as e:
        raise Exception(f"Error when upload dataset: {str(e)}")


def update_dataset_to_minio_by_id(dataset_id: str, dataName: str = None, dataType: str = None, file_data=None):
    parquet_stream = None
    try:

        # Lấy bản ghi hiện tại để so sánh
        current_data = data_collection.find_one({"_id": ObjectId(dataset_id)})
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

        if file_data and file_data.file:
            # Read file and change to DataFrame
            file_content_bytes = file_data.file.read()
            csv_stream = io.BytesIO(file_content_bytes)
            df = pd.read_csv(csv_stream)

            # Get dataset from MinIO
            parquet_stream = minIOStorage.get_object(bucket_name, object_name)
            df_retrieved = pd.read_parquet(parquet_stream)
            parquet_stream.close()

            if not df.equals(df_retrieved):
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
            data_collection.update_one(
                {"_id": ObjectId(dataset_id)},
                {"$set": update_fields}
            )
            
        return data_changed

    except Exception as e:
        parquet_stream.close() if parquet_stream else None
        raise Exception(f"Error: {str(e)}")


def delete_dataset_at_minio_by_id(dataset_id: str):
    dataset = data_collection.find_one({"_id": ObjectId(dataset_id)}, {"data_link": 1})
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
            dataset_mongo_result = data_collection.delete_one({"_id": ObjectId(dataset_id)})
            
            if dataset_mongo_result.deleted_count == 1:
                return True
            else:
                raise Exception("Removed MinIO file, but error when removing MongoDB metadata")
        else:
            raise Exception("Remove MinIO file failure")

    except Exception as e:
        raise Exception(f"Error when removing: {str(e)}")


def update_dataset_by_id(dataset_id: str, dataName: str = None, dataType: str = None, file_data=None):
    try:
        # Lấy bản ghi hiện tại để so sánh
        current_data = data_collection.find_one({"_id": ObjectId(dataset_id)})
        if not current_data:
            raise HTTPException(status_code=404, detail="Không tìm thấy bộ dữ liệu")

        update_fields = {}

        # Kiểm tra từng trường và chỉ thêm vào nếu có thay đổi
        if dataName and dataName != current_data.get("dataName"):
            update_fields["dataName"] = dataName
        if dataType and dataType != current_data.get("dataType"):
            update_fields["dataType"] = dataType
        if file_data:
            encoded_file = encode_csv_to_base64(file_data)
            if encoded_file != current_data.get("dataFile"):
                update_fields["dataFile"] = encoded_file

        if not update_fields:
            return {"message": "⚠️Không có thay đổi nào"}

        update_fields["latestUpdate"] = time.time()

        data_collection.update_one(
            {"_id": ObjectId(dataset_id)},
            {"$set": update_fields}
        )
            
        return {"message": "✅ Cập nhật thành công"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi cập nhật: {str(e)}")

    
def delete_dataset_by_id(dataset_id: str):
    try:
        result = data_collection.delete_one({"_id": ObjectId(dataset_id)})
        if result.deleted_count == 1:
            return {"message": "Xóa bộ dữ liệu thành công"}
        else:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy bộ dữ liệu cần xóa"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi khi xóa dữ liệu: {str(e)}")

# Hàm lấy danh sách data user cho admin
def get_user_data_list():
    try:
        data_list = data_collection.find({"userId": {"$ne": "0"}})
        result = [serialize_mongo_doc(data) for data in data_list]
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy danh sách dữ liệu: {str(e)}")
