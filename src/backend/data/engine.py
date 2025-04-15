from pydantic import BaseModel
from typing import List, Dict
from bson import ObjectId
from datetime import datetime
from database.database import get_database

import base64
import pandas as pd
import io

db = get_database()
data_collection = db["tbl_Data"]


# Giả lập dữ liệu
class DataInfo(BaseModel):
    _id: str
    dataName: str
    dataType: str
    role: str
    dataFile: str
    latestUpdate: str
    createDate: str
    attributes: List[str]
    target: str


# Dữ liệu JSON giả lập
data = {
    "_id": str(ObjectId("67a63bde43fdecfc96c744e7")),
    "dataName": "iris data",
    "dataType": "table",
    "role": "Admin",
    "dataFile": "iris.data.csv",
    "latestUpdate": "08/02/2025",
    "createDate": "05/02/2025",
    "attributes": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
    "target": "class",
}


# Hàm chuyển đổi objectID thành chuỗi
def data_helper(data) -> dict:
    return {
        "_id": str(data["_id"]),
        "dataName": str(data["dataName"]),
        "dataType": str(data["dataType"]),
        "role": str(data["role"]),
        "dataFile": str(data["dataFile"]),
        "latestUpdate": str(data["latestUpdate"]),
        "createDate": str(data["createDate"]),
        "attributes": str(data["attributes"]),
        "target": str(data["target"]),
    }


# Hàm lấy danh sách data
def get_list_data():
    data = data_collection.find()  # Sử dụng find() để lấy tất cả các bản ghi
    list_data = []
    for item in data:
        item["_id"] = str(item["_id"])  # Chuyển ObjectId sang chuỗi trước khi trả về
        list_data.append(item)
    return list_data


def encode_csv_to_base64(file_path):
    with open(file_path, "rb") as file:
        encoded_data = base64.b64encode(file.read()).decode("utf-8")
    return encoded_data


def decode_base64_to_dataframe(base64_string):
    # Giai ma Base64 thanh du lieu nhi phan
    decoded_bytes = base64.b64decode(base64_string)

    # Chuyen du lieu nhi phan thanh doi tuong giong file (stringIO)
    decoded_buffer = io.StringIO(decoded_bytes.decode("utf-8"))

    # Doc du lieu vao DataFrame
    df = pd.read_csv(decoded_buffer)

    return df
