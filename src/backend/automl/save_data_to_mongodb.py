import pymongo
import pandas as pd
import yaml

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["data_automl"]
csv_collection = db["file_csv"]
yml_collection = db["file_yaml"]

csv_file_path = "docs\data\glass.csv"
df = pd.read_csv(csv_file_path)
csv_data = df.to_dict(orient='records')
csv_collection.insert_many(csv_data)

yml_file_path = "docs\data\config.yml"
with open(yml_file_path, 'r') as yml_file:
    yml_data = yaml.safe_load(yml_file)
    yml_collection.insert_one(yml_data)

print("Dữ liệu đã được lưu vào MongoDB")