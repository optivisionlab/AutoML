from pydantic import BaseModel
from database.database import get_database
db = get_database()
users_collection = db['tbl_User']


class User(BaseModel):
    username: str
    email: str
    password: str
    gender: str
    date: str
    number: int
    role: str
    avatar: str

# Định nghĩa mô hình cho dữ liệu đầu vào
class LoginRequest(BaseModel):
    username: str
    password: str

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

import threading
from datetime import datetime, timedelta
def save_otp(username, value_otp):
    create_at_otp = datetime.now()  # Lưu trữ thời gian theo múi giờ UTC
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
        current_time = datetime.now()
        if (current_time-create_at_otp).total_seconds() <= 60:
            return True
        else:
            return False
    else:
        False
        
