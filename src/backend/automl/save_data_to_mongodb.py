import pymongo
import pandas as pd
import yaml
from pathlib import Path
import os
from database.database import get_database


client = get_database()
db = client["AutoML"]
csv_collection = db["file_csv"]
yml_collection = db["file_yaml"]
root_path = "assets/end_users"
csv_file_path = os.path.join(root_path, 'glass.csv')
yml_file_path = os.path.join(root_path, 'config_glass_nguoi_dung_tai_len.yml')

df = pd.read_csv(csv_file_path)
csv_data = df.to_dict(orient='records')
csv_collection.insert_many(csv_data)

with open(yml_file_path, 'r') as yml_file:
    yml_data = yaml.safe_load(yml_file)
    yml_collection.insert_one(yml_data)

print("Dữ liệu đã được lưu vào MongoDB")
