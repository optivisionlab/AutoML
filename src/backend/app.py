from fastapi import FastAPI, UploadFile, File, status, HTTPException, Form
import cv2, datetime, os, tempfile, uvicorn, uuid
import numpy as np
from typing import List
from fastapi.responses import JSONResponse
from io import BytesIO
import pandas as pd
from users.engine import checkLogin
import pathlib
from automl.engine import get_config, train_process, get_data_and_config_from_MongoDB
<<<<<<< HEAD

=======
>>>>>>> binhdev

# default sync
app = FastAPI()

@app.get("/")
def ping():
    return{
        "AutoML": "version 1.0",
        "message": "Hi there :P"
    }

# @app.post("/login")
# def api_login(username: str = Form(...), password: str = Form(...)):
#     message = "This is Users"
#     if username == "Admin" and password == "Admin":
#         message = "This is Admin"
#     return{
#         "username": username,
#         "password": password,
#         "message": message
#     }
@app.post("/upload-files")
def api_login(files: List[UploadFile] = File(...), sep: str = Form(...)):
    
    """
        file: test.csv
        stem => test
        suffix => .csv
    """

    data_list = []
    files_list = []
    for file in files:
        if pathlib.Path(os.path.basename(file.filename)).suffix != ".csv":
            data_list.append(None)
            files_list.append(file.filename)
            continue

        files_list.append(file.filename)
        contents = file.file.read()
        data = BytesIO(contents)
        df = pd.read_csv(data, on_bad_lines='skip', sep=sep, engine='python')
        data_list.append(df.values.tolist())
        data.close()
        file.file.close()

    return {
        "data_list": data_list,
        "files_list": files_list
    } 

#Nam api user
from users.engine import User
from database.database import get_database
from users.engine import user_helper
from users.engine import users_collection




#Lấy danh sách user
from users.engine import get_list_user
@app.get("/users")
def get_users():
    list_user = get_list_user()
    return list_user

from users.engine import check_exits_username
#Lấy 1 user
@app.get("/users/{username}")
def get_user(username):
    if check_exits_username(username):
        existing_user = users_collection.find_one({"username": username})
        return user_helper(existing_user)
    else:
        return {"message": f"Người dùng {username} không tồn tại"}



from users.engine import checkLogin
@app.post("/login")
def login(username, password):
    if checkLogin(username, password):
        user = users_collection.find_one({"username": username}) 
        if user['role'] == "Admin":
            message = "This is Admin"
        else:
            message = "This is User"
        return {
            "Hello": f"Xin chào {username}",
            "message": message
        }
    else:
        return {"message": "Tài khoản mật khẩu không chính xác!"}


#Thêm user, đăng kí user mới
@app.post("/signup")
def singup(new_user : User):
    if check_exits_username(new_user.username):
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

#update user
@app.put("/update/{username}")
def update_user(username: str, new_user: User):
    if check_exits_username(username):
        old_user = users_collection.find_one({"username": username})
        new_value = {"$set": new_user.dict()}
        result = users_collection.update_one({"_id": old_user["_id"]},new_value )

        if result.modified_count > 0:
            return {'message': f'Thông tin người dùng {username} đã được cập nhật'}
        else:
            return {'message': f'Không thể cập nhật thông tin người dùng {username}'}
    else:
        return {"message": f"Người dùng {username} không tồn tại"}

from users.engine import send_reset_password_email

@app.post("/forgot_password/{email}")
def forgot_password(email: str):
    user = users_collection.find_one({"email":email})
    if user:
        send_reset_password_email(email, user['password'])
        return {"message": f"Password đã gửi về email: {email}"}
    else:
        return {"message": f"Người dùng {email} không tồn tại"}

from users.engine import save_otp, send_otp, generate_otp
@app.post("/send_email/{username}")
def send_email(username: str):
    user = users_collection.find_one({"username":username})
    if user:
        otp = generate_otp()
        save_otp(username,otp )
        send_otp(user['email'], otp)
        return {"message": f"OTP đã gửi về email: {user['email']}"}
    else:
        return {"message": f"Người dùng {username} không tồn tại"}


from users.engine import check_time_otp 
@app.post("/verification_email/{username}")
def verification_email(username: str, otp: str):
    user = users_collection.find_one({"username":username})
    if user:
        if otp == user['otp']:
            if check_time_otp(username):
                return {"message": f"Xác thực email {user['email']} thành công"}
            else:
                return {"message": "OTP hết hiệu lực"}
        else:
            return {"message": "OTP không chính xác"}
    else:
        return {"message": f"Người dùng {username} không tồn tại"}

@app.post("/training-file-local")
def api_train1(file_data: UploadFile, file_config : UploadFile):
    
    contents = file_data.file.read()
    data_file = BytesIO(contents)
    data = pd.read_csv(data_file)

    contents = file_config.file.read()
    data_file = BytesIO(contents)
    choose, list_model_search, list_feature, target, matrix,models = get_config(data_file)
    best_model_id, best_model ,best_score, best_params = train_process(data, choose, list_model_search, list_feature, target,matrix,models)
    
    return {
        "best_model_id": best_model_id,
        "Best Model: ": str(best_model),
        "Best Params: ": best_params,
        "Best Score: ": best_score
    } 

@app.post("/training-file-mongodb")
def api_train2():
    data, choose, list_model_search, list_feature, target,matrix,models = get_data_and_config_from_MongoDB()
    best_model_name, best_model ,best_score, best_params = train_process(data, choose, list_model_search, list_feature, target,matrix,models)
    
    return {
        "Best Model Name: ": best_model_name,
        "Best Model: ": str(best_model),
        "Best Params: ": best_params,
        "Best Score: ": best_score
    } 



if __name__ == "__main__":
    
    uvicorn.run('app:app', host="0.0.0.0", port=9999, reload=True)
    pass