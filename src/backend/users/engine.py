
import time
from pydantic import BaseModel
from typing import Optional
from database.database import get_database
from fastapi import Form
db = get_database()
users_collection = db['tbl_User']
contacts_collection = db["tbl_contacts"]

class User(BaseModel):
    username: str
    email: str
    password: str
    gender: str
    date: str
    number: str
    role: Optional[str] = "User"
    avatar: Optional[str] = None
    
# Định nghĩa mô hình cho dữ liệu đầu vào
class LoginRequest(BaseModel):
    username: str
    password: str
    
class ChangePassword(BaseModel):
    password: str
    new1_password: str 
    new2_password: str

    #Hàm chuyển đổi objectID thành chuỗi
def user_helper(user) -> dict:
    return{
        "_id": str(user["_id"]),
        "username": str(user["username"]),
        "email": str(user["email"]),
        # "Password": str(user["password"]),
        "gender": str(user["gender"]),
        "date": str(user["date"]),
        "number": str(user["number"]),
        "role": str(user["role"]),
        "avatar": str(user["avatar"])
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
        return existing_user
    else:
        return False
    
def check_exits_email(email):
    existing_email = users_collection.find_one({"email": email})
    if existing_email:
        return existing_email
    else:
        return False

#Hàm kiểm tra username , password 
def checkLogin(username, password):
    check_user = users_collection.find_one({"username": username})
    check_email = users_collection.find_one({"email": username})
    user = check_user if check_user else check_email
    if user:
        if user['password'] == password:
            return user
        else:
            return False
    else:
        return False
   

import jwt 
   
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 30      
   
def check_token(token):
    try:
        # Giải mã token và xác thực chữ ký
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Kiểm tra xem token có tồn tại trong cơ sở dữ liệu không
        token_user = users_collection.find_one({"username": payload['sub'], "token": token})
        
        if token_user:
            return token_user  # Trả về thông tin người dùng
        else:
            return None  # Token không tồn tại trong cơ sở dữ liệu
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn!")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ!")
    
from fastapi import HTTPException, status, Depends, Header
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")    
def get_current_user(token: str = Depends(oauth2_scheme)):
    user_data = check_token(token)  # Hàm validate_token cần được định nghĩa
    if user_data is None:
        raise HTTPException(status_code=401, detail="Token không hợp lệ!")
    return user_data
    
def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get('role') != 'Admin':
        raise HTTPException(status_code=403, detail="Quyền truy cập bị từ chối!")
    return current_user  
    

def handleLogin(username, password):
    if checkLogin(username, password):
        user = checkLogin(username, password)
        if user['role'] == "Admin" :
            message = "This is Admin"
            role = user.get('role', 'Admin')
            token = create_access_token(data={"sub": username, "role": role})
            update_user = {"$set":{
                "token": token
            }}
            users_collection.update_one({"username": username}, update_user)
        else:
            message = "This is User"
            role = user.get('role', 'User')
            token = create_access_token(data={"sub": username, "role": role})
            update_user = {"$set":{
                "token": token
            }}
            
            users_collection.update_one({"username": username}, update_user)

        user_login = {
            "username": user['username'],
            "email": user['email'],
            "gender": user['gender'],
            "date": user['date'],
            "number": user['number'],
            "role": role
        }
        return user_login
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản hoặc mật khẩu không chính xác!"
        )
        # message = {
        #     "massage": "Tài khoản mật khẩu không chính xác!"
        # }
        # return message
    
from email.mime.text import MIMEText
import smtplib
import uuid

def send_reset_password_email(email, token):
    # Thay thế thông tin SMTP của bạn
    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = "devweb3010@gmail.com"
    password = "mrpk pqih agjd atou"

    message = MIMEText(f"Your reset password: {token}")
    message['From'] = sender_email
    message['To'] = email
    message['Subject'] = "Reset Password"

    with smtplib.SMTP(smtp_server, port) as server:
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, email, message.as_string())


import random
def generate_otp():
    length_otp = 6
    digits = "0123456789"
    otp = ""
    for i in range(length_otp):
        otp += digits[random.randint(0, 9)]
    return otp

def remove_otp(username):
    update = {"$set":{
        "otp": "",
        "createAtOTP": ""
    }}
    users_collection.update_one({"username": username},update)


from datetime import datetime
def save_otp(username, value_otp):
    create_at_otp = datetime.datetime.now()  # Lưu trữ thời gian theo múi giờ UTC
    value_set = {"$set":{
        "otp": value_otp,
        "createAtOTP": create_at_otp
    }}

    # delay_time_seconds = 15
    # auto_remove = threading.Timer(delay_time_seconds, remove_otp(username))
    # auto_remove.start()
    users_collection.update_one({"username": username},value_set)
    

    
def send_otp(email, otp):
    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = "devweb3010@gmail.com"
    password = "xkda ehrw nedr djqo"

    message = MIMEText(f"OTP của bạn là : {otp}")
    message['From'] = sender_email
    message['To'] = email
    message['Subject'] = "Xác thực Email"

    with smtplib.SMTP(smtp_server, port) as server:
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, email, message.as_string())


def check_time_otp(username):
    user = users_collection.find_one({"username": username})
    if user:
        create_at_otp  = user['createAtOTP']
        current_time = datetime.datetime.now()
        if (current_time-create_at_otp).total_seconds() <= 60:
            return True
        else:
            return False
    else:
        False


def handle_change_password(username, pw, new_pw1, new_pw2):
    user = users_collection.find_one({"username": username})
    if user:
        if pw == user['password']:
            if new_pw1 == new_pw2:
                value_set = {"$set":{
                    "password": new_pw1
                }}
                users_collection.update_one({"_id": user["_id"]}, value_set)
                raise HTTPException(
                    status_code=status.HTTP_200_OK,
                    detail=f"Thay đổi mật khẩu thành công!"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mật khẩu mới chưa trùng khớp!"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Mật khẩu không chính xác!"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )
    
    
import base64, io
from fastapi.responses import StreamingResponse
def handle_update_avatar(username, avatar):
    user = users_collection.find_one({"username": username})
    if user:
        # avatar_data = avatar.read()
        avatar_data = avatar.file.read()
        avatar_base64 = base64.b64encode(avatar_data).decode('utf-8') 
        avatar_set = {"$set":{
            "avatar": avatar_base64
        }}
        users_collection.update_one({"_id": user["_id"]}, avatar_set)
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail="Avatar cập nhật thành công"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )
    
def handle_get_avatar(username):
    user = users_collection.find_one({"username": username})
    if user and "avatar":
        avatar_base64 = user['avatar']
        avatar_data = base64.b64decode(avatar_base64)
        
        return StreamingResponse(io.BytesIO(avatar_data), media_type="image/png")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )
    
    
# def handle_signup(new_user: User):
#     if check_exits_username(new_user.username) or check_exits_email(new_user.email):
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="Người dùng đã tồn tại!"
#         )

#     result = users_collection.insert_one(new_user.dict())
#     # print(result)
#     if result.inserted_id:
#         raise HTTPException(
#             status_code=status.HTTP_200_OK,
#             detail=f"Đăng ký thành công user: {new_user.username}"
#         )
#     else:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail='Đã xảy ra lỗi khi thêm người dùng'
#         )
    
from fastapi.responses import JSONResponse   
def handle_signup(new_user: User):
    if check_exits_username(new_user.username) or check_exits_email(new_user.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Người dùng đã tồn tại!"
        )

    result = users_collection.insert_one(new_user.dict())
    # print(result)
    if result.inserted_id:
        return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "username": new_user.username,
            "email": new_user.email,
            "gender": new_user.gender,
            "date": new_user.date,
            "number": new_user.number,
            "role": new_user.role,
            "avatar": new_user.avatar
        }
    )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Đã xảy ra lỗi khi thêm người dùng'
        )
    
    
    
def handle_delete_user(username):
    result = users_collection.delete_one({"username": username })
    # print(result)
    if result.deleted_count > 0:
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail=f"Người dùng {username} đã xóa"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không thể xóa người dùng {username}. Người dùng không tồn tại hoặc đã xảy ra lỗi"
        )

def handle_update_user(username, new_user: User):
    if check_exits_username(username):
        old_user = users_collection.find_one({"username": username})
        new_value = {"$set": new_user.dict()}
        result = users_collection.update_one({"_id": old_user["_id"]},new_value )

        if result.modified_count > 0:
            raise HTTPException(
                status_code=status.HTTP_200_OK,
                detail=f'Thông tin người dùng {username} đã được cập nhật'
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Không thể cập nhật thông tin người dùng {username}'
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )
    
def handle_forgot_password(email):
    user = users_collection.find_one({"email":email})
    if user:
        send_reset_password_email(email, user['password'])
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail=f"Password đã gửi về email: {email}"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {email} không tồn tại"
        )
    
def handle_send_otp(username):
    user = users_collection.find_one({"username":username})
    if user:
        otp = generate_otp()
        save_otp(username,otp)
        send_otp(user['email'], otp)
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail=f"OTP đã gửi về email: {user['email']}"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )
    
    
def handle_verification_email(username, otp):
    user = users_collection.find_one({"username":username})
    if user:
        if otp == user['otp']:
            if check_time_otp(username):
                raise HTTPException(
                    status_code=status.HTTP_200_OK,
                    detail=f"Xác thực email {user['email']} thành công"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OTP hết hiệu lực"
                )
        else:
            raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OTP không chính xác"
                )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )

import datetime     
        
def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
def handle_contact(username: str, email: str, message: str):
    user = users_collection.find_one({"username": username, "email": email})
    if user:
        smtp_server = "smtp.gmail.com"
        port = 587
        sender_email = "devweb3010@gmail.com"  # Thay bằng email thật
        sender_password = "xkda ehrw nedr djqo"  # Thay bằng mật khẩu thật hoặc dùng App Password
        receiver_email = "admin@gmail.com" # Thay email admin

        msg = MIMEText(f"Từ: {username}\nEmail: {email}\n\nNội dung:\n{message}")
        msg["Subject"] = "Trợ giúp người dùng"
        msg["From"] = sender_email
        msg["To"] = receiver_email

        try:
            # Gửi email
            with smtplib.SMTP(smtp_server, port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, msg.as_string())

            # Lưu vào collection liên hệ
            contact_data = {
                "username": username,
                "email": email,
                "message": message,
                "created_at": time.time()
            }
            contacts_collection.insert_one(contact_data)

            return {
                "status": "success",
                "message": "Liên hệ đã được gửi và lưu thành công."
            }

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Lỗi khi gửi email hoặc lưu liên hệ: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy người dùng với username và email đã cung cấp."
        )