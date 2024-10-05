from fastapi import FastAPI, UploadFile, File, status, HTTPException, Form
import cv2, datetime, os, tempfile, uvicorn, uuid
import numpy as np
from typing import List
from fastapi.responses import JSONResponse
from io import BytesIO
import pandas as pd
from users.engine import checkLogin
import pathlib
from pydantic import BaseModel
import csv
from users.connect_db import get_database
import base64

# default sync
app = FastAPI()

@app.get("/")
def ping():
    return{
        "AutoML": "version 1.0",
        "message": "Hi there :P"
    }


@app.post("/login")
def api_login(username: str = Form(...), password: str = Form(...)):

    if checkLogin(username=username, pwd=password):
        message = "Login OKE >>> "

    message += "This is Users"
    if username == "Admin" and password == "Admin":
        message += "This is Admin"

    return{
        "username": username,
        "password": password,
        "message": message
    }


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

###CHINH SUA THONG TIN
# class UserInfor(BaseModel):
#     id: str
#     full_name: str
#     email: str
#     gender: str
#     birthday: str
#     phone: str

# @app.put("/update_user_info")
# def update_user_info(files: List[UploadFile] = File(...), sep: str = Form(...), user_update = UserInfor, full_name: str = Form(...), email: str = Form(...), gender: str = Form(...), birthday: str = Form(...), phone: str = Form(...)):
    
#     """
#         file: test.csv
#         stem => test
#         suffix => .csv
#     """

#     data_list = []
#     files_list = []
#     for file in files:
#         filename = os.path.basename(file.filename)
#         if pathlib.Path(os.path.basename(file.filename)).suffix != ".csv":
#             data_list.append(None)
#             files_list.append(file.filename)
#             continue

#         files_list.append(file.filename)
#         contents = file.file.read()
#         data = BytesIO(contents)
#         df = pd.read_csv(data, on_bad_lines='skip', sep=sep, engine='python')
#         # Chỉnh sửa thông tin người dùng từ các thông số truyền vào
#         for index, row in df.iterrows():
#             if row['email'] == user_update.email:
#                 df.at[index, 'full_name'] = full_name
#                 df.at[index, 'gender'] = gender
#                 df.at[index, 'birthday'] = birthday
#                 df.at[index, 'phone'] = phone
#                 updated_user_info = UserInfor(
#                     email=row['email'],
#                     full_name=full_name,
#                     gender=gender,
#                     birthday=birthday,
#                     phone=phone
#                 )
#                 data_list.append(updated_user_info)
#             else:
#                 user_info = UserInfor(
#                     email=row['email'],
#                     full_name=row['full_name'],
#                     gender=row['gender'],
#                     birthday=row['birthday'],
#                     phone=row['phone']
#                 )
#                 data_list.append(user_info)
        
#         # Ghi lại dữ liệu đã chỉnh sửa vào file CSV
#         df.to_csv(filename, index=False)
#         data_list.append(df.values.tolist())
#         data.close()
#         file.file.close()

#     return {
#         "data_list": data_list,
#         "files_list": files_list
#     }

###CHINH SUA THONG TIN

class UserInfor(BaseModel):
    user_id: str
    full_name: str
    email: str
    gender: str
    birthday: str
    phone: str

dbname = get_database()
collection_user = dbname['Tbl_User'] # collection name

@app.put("/users/{user_id}")
def update_user(user_id: str, user_data: UserInfor):
    updated_user = {
        "full_name": user_data.full_name,
        "email": user_data.email,
        "gender": user_data.gender,
        "birthday": user_data.birthday,
        "phone": user_data.phone
    }
    
    result = collection_user.update_one({"_id": user_id}, {"$set": updated_user})
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
    
    return {"message": "Cập nhật thông tin người dùng thành công"}

# Bộ dữ liệu của bạn
class YourData(BaseModel):
    ID: str
    name_data: str
    type_data: str
    date_create: str
    date_update: str

collection_ydata = dbname['Tbl_yourdata']

@app.put("/du_lieu_cua_ban/{ID}")
def update_yourdata(yourdata_id: str, your_data: YourData):
    updated_your_data = {
        "name_data": your_data.name_data,
        "type_data": your_data.type_data,
        "date_create": your_data.date_create,
        "date_update": your_data.date_update
    }
    
    result = collection_ydata.update_one({"_id": yourdata_id}, {"$set": your_data})
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Dữ liệu không tồn tại")
    
    return {"message": "Cập nhật thông tin dữ liệu người dùng thành công"}

#Xoa bộ dữ liệu
@app.delete("/du_lieu_cua_ban/{ID}")
def delete_yourdata(yourdata_id: str):
    y_data = collection_ydata.find_one({"_id": yourdata_id})
    if y_data is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ dữ liệu trên")

    result = collection_ydata.delete_one({"_id": yourdata_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Xóa bộ dữ liệu thất bại")
    
    return {"message": "Xóa thành công bộ dữ liệu"}
#Thêm bộ dữ liệu
@app.post("/add_data")
async def add_data(file: UploadFile = File(...), category: str = Form(...)):

    if category == "table":
        contents = await file.read()
        df = pd.read_csv(contents)
        return JSONResponse(content={"message": "Dữ liệu dạng bảng được thêm thành công"})
    
    elif category == "image":
        contents = await file.read()
        image_data = base64.b64encode(contents).decode("utf-8")
        return JSONResponse(content={"message": "Dữ liệu dạng ảnh được thêm thành công"})
    
    elif category == "text":
        text_data = await file.read()
        return JSONResponse(content={"message": "Dữ liệu dạng text được thêm thành công"})
    
    elif category == "video":
        contents = await file.read()
        return JSONResponse(content={"message": "Dữ liệu dạng video được thêm thành công"})

    return JSONResponse(content={"error": "Dạng dữ liệu bạn chọn không phù hợp"})

# Sửa mô hình của bạn
@app.put("/du_lieu_cua_ban/{ID}")
def update_model(ID: str, new_name_data: str):
    query = {"ID": ID}
    new_name = {"$set": {"name": new_name_data}}

    result = collection_ydata.update_one(query, new_name)
    
    if result.modified_count > 0:
        return {"message": "Tên mô hình đã được cập nhật"}
    else:
        return {"error": "Mô hình không tồn tại"}


if __name__ == "__main__":
    uvicorn.run('app:app', host="0.0.0.0", port=9999, reload=True)
    pass
