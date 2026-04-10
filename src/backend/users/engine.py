import time
import datetime
import secrets
from email.mime.text import MIMEText
import smtplib
from pydantic import BaseModel
from typing import Optional
from pymongo.asynchronous.database import AsyncDatabase
from dotenv import load_dotenv
from fastapi import HTTPException, status
from users.utils.email_service import email_service

# Load file .env
load_dotenv()


class User(BaseModel):
    username: str
    email: str
    password: str
    gender: str
    date: str
    number: str
    fullName: str
    role: Optional[str] = None
    avatar: Optional[str] = None


class UpdateUser(BaseModel):  # Dùng cho cập nhật thông tin người dùng
    email: Optional[str]
    gender: Optional[str]
    date: Optional[str]
    fullName: Optional[str]
    number: Optional[str]


# Hàm chuyển đổi objectID thành chuỗi
def user_helper(user) -> dict:
    return{
        "_id": str(user["_id"]),
        "username": str(user["username"]),
        "email": str(user["email"]),
        # "Password": str(user["password"]),
        "gender": user["gender"],
        "date": user["date"],
        "number": user["number"],
        "fullName": str(user["fullName"]),
        "role": str(user["role"]),
        "avatar": user.get('avatar')
    }


# Hàm lấy danh sách user
async def get_list_user(db: AsyncDatabase):
    users_collection = db.tbl_User

    users_data = await users_collection.find({"role": "user"}, {"password": 0}).to_list(length=None)  # Lọc theo role
    list_user = []
    for user in users_data:
        user['_id'] = str(user['_id'])  # Convert ObjectId to string
        list_user.append(user)
    return list_user


# Hàm kiểm tra sự tồn tại user
async def check_exits_username(username, db: AsyncDatabase):
    users_collection = db.tbl_User

    existing_user = await users_collection.find_one({"username": username}, {"password": 0})
    if existing_user:
        return existing_user
    else:
        return False


def generate_otp(length: int = 6) -> str:
    """Generates a cryptographically secure OTP"""
    return "".join(secrets.choice("0123456789") for _ in range(length))


async def remove_otp(email: str, db: AsyncDatabase):
    await db.tbl_User.update_one(
        {"email": email},
        {"$unset": {"otp_code": "", "otp_expires_at": ""}}
    )


async def save_otp(email: str, otp: str, db: AsyncDatabase):
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
    
    await db.tbl_User.update_one(
        {"email": email},
        {
            "$set": {
                "otp": otp,
                "createAtOTP": expires_at.timestamp()
            }
        }
    )


async def handle_send_otp(email, db: AsyncDatabase):
    otp = generate_otp()

    await save_otp(email, otp, db)
    email_service.send_otp(email, otp)

    return {
        "message": f"OTP đã gửi về email: {email}"
    }


async def handle_change_password(user, current_password: str, new_password: str, db: AsyncDatabase):
    if user.get('password'):
        if current_password != user.get('password'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )

        await db.tbl_User.update_one(
            {"_id": user['_id']},
            {"$set": {'password': new_password}}
        )
        return {"message": "Change password successfully"}
    else:
        linked_acc = await db.linked_accounts.find_one({'user_id': user['_id']})

        if not linked_acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found in linked accounts"
            )
        
        if current_password != linked_acc.get('password'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )

        await db.linked_accounts.update_one(
            {"_id": linked_acc['_id']},
            {"$set": {'password': new_password}}
        )
        return {"message": "Change password successfully"}

    
import base64, io
from fastapi.responses import StreamingResponse
async def handle_update_avatar(username, avatar, db: AsyncDatabase):
    users_collection = db.tbl_User
    user = await users_collection.find_one({"username": username})
    if user:
        # avatar_data = avatar.read()
        avatar_data = avatar.file.read()
        avatar_base64 = base64.b64encode(avatar_data).decode('utf-8')
        # avatar_with_prefix = f"data:image/jpeg;base64,{avatar_base64}"
        avatar_set = {"$set": {
            "avatar": avatar_base64
        }}
        await users_collection.update_one({"_id": user["_id"]}, avatar_set)
        raise HTTPException(
            status_code=status.HTTP_200_OK,
            detail="Avatar cập nhật thành công"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )

    
async def handle_get_avatar(username, db: AsyncDatabase):
    users_collection = db.tbl_User
    user = await users_collection.find_one({"username": username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User not found"
        )
    
    avatar_base64 = user.get('avatar')
    if not avatar_base64:
        return None
    
    try:
        avatar_data = base64.b64decode(avatar_base64)
        return StreamingResponse(io.BytesIO(avatar_data), media_type="image/png")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image data on database is corrupted {str(e)}"
        )


async def handle_delete_user(username, db: AsyncDatabase) -> dict:
    users_collection = db.tbl_User

    user_exist = await users_collection.find_one({'username': username})

    linked_acc = await db.linked_accounts.delete_many({'user_id': user_exist['_id']})
    result = await users_collection.delete_one({"username": username })
    
    if result.deleted_count > 0 and linked_acc > 0:
        return {"message": "Deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không thể xóa người dùng {username}. Người dùng không tồn tại hoặc đã xảy ra lỗi"
        )


async def handle_update_user(username: str, new_user: UpdateUser, db: AsyncDatabase):
    users_collection = db.tbl_User
    check_username = await check_exits_username(username, db)

    if check_username:
        old_user = await users_collection.find_one({"username": username}, {"password": 0})
        new_value = {"$set": new_user.model_dump()}
        result = await users_collection.update_one({"_id": old_user["_id"]}, new_value)

        if result.modified_count > 0:
            return {"message": f"Thông tin người dùng {username} đã được cập nhật"}
        elif result.matched_count > 0:
            return {"message": f"Thông tin người dùng {username} không có thay đổi nào"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy người dùng {username} để cập nhật"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại"
        )


async def handle_contact(fullname: str, email: str, message: str, db: AsyncDatabase):
    contacts_collection = db.tbl_contacts

    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = "devweb3010@gmail.com"  # Thay bằng email thật
    sender_password = "xkda ehrw nedr djqo"  # Thay bằng mật khẩu thật hoặc dùng App Password
    receiver_email = "mykhanh03102003@gmail.com" # Thay email admin

    msg = MIMEText(f"Từ: {fullname}\nEmail: {email}\n\nNội dung:\n{message}")
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
            "fullname": fullname,
            "email": email,
            "message": message,
            "created_at": time.time()
        }
        await contacts_collection.insert_one(contact_data)

        return {
            "status": "success",
            "message": "Liên hệ đã được gửi và lưu thành công."
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi gửi email hoặc lưu liên hệ: {str(e)}"
        )
