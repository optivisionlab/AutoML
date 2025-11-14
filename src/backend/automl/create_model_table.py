from database.database import connection
import asyncio

client = asyncio.run(connection())

db = client["AutoML"]
model_collection = db["Classification_models"]


keys = ['0', '1', '2', '3', '4', '5']
document = {"model_keys": keys}

# Chèn tài liệu vào MongoDB
result = model_collection.insert_one(document)

print("Id của các model đã được lưu vào MongoDB")
