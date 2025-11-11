from pymongo import AsyncMongoClient
from fastapi import Request
import os
from dotenv import load_dotenv


# Load file .env
load_dotenv()


async def connection():
    client = AsyncMongoClient(
        os.getenv('MONGODB_CONNECT', 'localhost:27017')
    )
    return client['AutoML'], client


async def get_db(request: Request):
    return request.app.state.db


if __name__ == "__main__":
    dbname = connection()
    # Kiểm tra kết nối đã được thiết lập thành công hay không
    if dbname is not None:
        print("Kết nối đến cơ sở dữ liệu MongoDB thành công.")
    else:
        print("Kết nối đến cơ sở dữ liệu MongoDB không thành công.")
