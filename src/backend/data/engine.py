from pydantic import BaseModel
from typing import List
from database.database import get_database
from bson.objectid import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId

import base64
import pandas as pd
import io
import time

db = get_database()
data_collection = db["tbl_Data"]


# Hàm lấy danh sách data
def get_datas(id_user):
    data = data_collection.find({"userId": id_user})
    list_data = []
    for item in data:
        item["_id"] = str(item["_id"])
        list_data.append(item)
    return list_data


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

    data_to_insert = {
        "dataName": dataName,
        "dataType": dataType,
        "dataFile": encoded_file,
        "latestUpdate": now,
        "createDate": now,
        "list_feature": [],
        "target": None,
        "userId": userId,
    }

    result = data_collection.insert_one(data_to_insert)
    if result.inserted_id:
        serialize_mongo_doc(data_to_insert)
        return JSONResponse(content=data_to_insert)
    else:
        raise HTTPException(status_code=500, detail="Đã xảy ra lỗi thêm bộ dữ liệu")


def update_dataset_by_id(dataset_id: str, dataName: str = None, file_data=None):
    update_fields = {}

    if dataName is not None:
        update_fields["dataName"] = dataName

    if file_data is not None:
        encoded_file = encode_csv_to_base64(file_data)
        update_fields["dataFile"] = encoded_file
        update_fields["lastestUpdate"] = str(time.time())

    if not update_fields:
        raise HTTPException(status_code=400, detail="Không có dữ liệu nào để cập nhật")

    result = data_collection.update_one(
        {"_id": ObjectId(dataset_id)}, {"$set": update_fields}
    )

    if result.modified_count == 1:
        return {"message": "Cập nhật thành công"}
    else:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy bộ dữ liệu hoặc không có thay đổi nào",
        )


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
