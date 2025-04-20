from pydantic import BaseModel
from typing import List
from database.database import get_database
from bson.objectid import ObjectId

import base64
import pandas as pd
import io

db = get_database()
data_collection = db["tbl_Data"]


class Data(BaseModel):
    id: str
    dataName: str
    dataType: str
    dataFile: str
    lastestUpdate: str
    createDate: str
    list_feature: List[str]
    target: str
    userId: str


def data_helper(data) -> dict:
    return {
        "_id": str(data.get("_id", "")),
        "dataName": str(data["dataName"]),
        "dataType": str(data["dataType"]),
        "dataFile": str(data["dataFile"]),
        "lastestUpdate": str(data["lastestUpdate"]),
        "createDate": str(data["createDate"]),
        "list_feature": list(data["list_feature"]),
        "target": str(data["target"]),
        "userId": str(data["userId"]),
    }


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
