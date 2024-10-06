from pydantic import BaseModel
from database.database import get_database
db = get_database()
users_collection = db['tbl_User']


class User(BaseModel):
    username: str
    password: str
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

#Hàm lấy danh sách user
def get_list_user():
    users_data = users_collection.find()  # Sử dụng find() để lấy tất cả các bản ghi
    list_user = []
    for user in users_data:
        user['_id'] = str(user['_id'])  # Chuyển ObjectId sang chuỗi trước khi trả về
        list_user.append(user)
    return list_user

#Hàm kiểm tra sự tồn tại user
def check_exits_username(username):
    existing_user = users_collection.find_one({"username": username})
    if existing_user:
        return True
    else:
        return False


#Hàm kiểm tra username , password 
def checkLogin(username, password):
    check_user = users_collection.find_one({"username": username})
    if check_user:
        if check_user['password'] == password:
            return True
        else:
            return False
    else:
        return False