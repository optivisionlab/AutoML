import pymongo
import pandas as pd
import yaml
from pathlib import Path
import os
from database.database import get_database



client = get_database()
db = client["AutoML"]
model_collection = db["Classification_models"]


keys = ['0', '1', '2', '3', '4', '5']
document = {"model_keys": keys}

# Chèn tài liệu vào MongoDB
result = model_collection.insert_one(document)

print("Id của các model đã được lưu vào MongoDB")
