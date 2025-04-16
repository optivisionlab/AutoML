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

# Hàm lấy danh sách data
def get_datas():
    data = data_collection.find()  # Sử dụng find() để lấy tất cả các bản ghi
    list_data = []
    for item in data:
        item["_id"] = str(item["_id"])  # Chuyển ObjectId sang chuỗi trước khi trả về
        list_data.append(item)
    return list_data

def get_data_base64(user_id):
    try:
        # Tìm document trong collection tbl_Data có trường userId trùng với user_id
        data = data_collection.find_one({"userId": user_id})

        if data and 'dataFile' in data:
            return data['dataFile']
        else:
            return None

    except Exception as e:
        print(f"Đã xảy ra lỗi khi truy vấn MongoDB: {e}")
        return None

def decode_base64_to_dataframe(user_id):
    base64_string = get_data_base64(user_id=user_id)
    # Giai ma Base64 thanh du lieu nhi phan
    decoded_bytes = base64.b64decode(base64_string)

    # Chuyen du lieu nhi phan thanh doi tuong giong file (stringIO)
    decoded_buffer = io.StringIO(decoded_bytes.decode("utf-8"))

    # Doc du lieu vao DataFrame
    df = pd.read_csv(decoded_buffer)

    return df

def get_data_from_mongodb_by_userid(user_id):
    df = decode_base64_to_dataframe(user_id=user_id)
    class_names = df.iloc[:,-1].unique().tolist()
    return df, class_names
    