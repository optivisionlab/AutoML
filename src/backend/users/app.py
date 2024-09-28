
import cv2, datetime, os, tempfile, uvicorn, uuid
from connect_db import get_database
from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()

db = get_database()
users_collection = db['tbl_User']

@app.get("/")
def ping():
    return{
        "Hello" : "AutoML"
    }


#Lấy danh sách user
@app.get("/users")
def get_users():
    users_data = users_collection.find()  # Sử dụng find() để lấy tất cả các bản ghi
    list_user = []
    for user in users_data:
        user['_id'] = str(user['_id'])  # Chuyển ObjectId sang chuỗi trước khi trả về
        list_user.append(user)
    return list_user

#Lấy 1 user
@app.get("/users/{username}")
def get_user(username):
    # users_data = users_collection.find()  # Sử dụng find() để lấy tất cả các bản ghi
    # for user in users_data:
    #     user['_id'] = str(user['_id'])  # Chuyển ObjectId sang chuỗi trước khi trả về
    #     if(user['username'] == username):
    #         return user
    # return {"message": f"Người dùng {username} không tồn tại"}
    existing_user = users_collection.find_one({"username": username})
    if existing_user:
        return user_helper(existing_user)
    else:
        return {"message": f"Người dùng {username} không tồn tại"}


class User(BaseModel):
    username: str
    passworld: str
    gender: str
    date: str
    number: int
    role: str
    

#Hàm chuyển đổi objectID thành chuỗi
def user_helper(user) -> dict:
    return{
        "_id": str(user["_id"]),
        "username": str(user["username"]),
        # "Password": str(user["password"]),
        "gender": str(user["gender"]),
        "date": str(user["date"]),
        "number": str(user["number"]),
        "role": str(user["role"]),
    }



#Thêm user, đăng kí user mới
@app.post("/signup")
def singup(new_user : User):
    existing_user = users_collection.find_one({"username": new_user.username})
    # print(existing_user)
    if existing_user:
        return {"message": f"Người dùng {new_user.username} đã tồn tại"}

    result = users_collection.insert_one(new_user.dict())
    # print(result)
    if result.inserted_id:
        return {'message': f'Đăng ký thành công user: {new_user.username}'}
    else:
        return {'message': 'Đã xảy ra lỗi khi thêm người dùng'}



#Xóa user
@app.delete("/delete/{username}")
def delete_user(username):
    result = users_collection.delete_one({"username": username })
    # print(result)
    if result.deleted_count > 0:
        return {"message": f"Người dùng {username} đã xóa"}
    else:
        return {"message": f"Không thể xóa người dùng {username}. Người dùng không tồn tại hoặc đã xảy ra lỗi"}



if __name__ == "__main__":
    uvicorn.run('app:app', host="127.0.0.1", port=8888, reload=True)
    pass


