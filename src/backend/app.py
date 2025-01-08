from fastapi import FastAPI, UploadFile, File, Form, Query
from typing import List
from io import BytesIO
import pandas as pd
from users.engine import checkLogin
from automl.engine import get_config, train_process, get_data_and_config_from_MongoDB,get_data_config_from_json
from automl.engine import app_train_local
from automl.model import Item
from users.engine import User
from users.engine import user_helper
from users.engine import users_collection
from users.engine import checkLogin
from users.engine import LoginRequest
from users.engine import create_access_token
from users.engine import check_exits_username
from users.engine import send_reset_password_email
from starlette.config import Config
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from users.engine import ChangePassword
from users.engine import save_otp, send_otp, generate_otp
import io, yaml, time, json, os, uvicorn, pathlib, base64
from fastapi.responses import StreamingResponse
from users.engine import check_time_otp 


# default sync
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="!secret")
file_path = "temp.config.yml"
with open(file_path, "r") as f:
    data = yaml.safe_load(f)

config = Config(file_path)
oauth = OAuth(config)

# phương thức để đăng ký một dịch vụ OAuth
CONF_URL = 'https://accounts.google.com/.well-known/openid-configuration'
oauth.register(
    name='google',
    server_metadata_url=CONF_URL,  #lay thong tin tu may chu
    client_id = data['CLIENT_ID'],
    client_secret = data['CLIENT_SECRET'],
    client_kwargs={
        'scope': 'openid email profile',
        'redirect_url': 'http://localhost:9999/auth'
    }
)


@app.get("/home")
def ping():
    return{
        "AutoML": "version 1.0",
        "message": "Hi there :P"
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


#Lấy danh sách user
from users.engine import get_list_user
@app.get("/users")
def get_users():
    list_user = get_list_user()
    return list_user


#Lấy 1 user
@app.get("/users/")
def get_user(username: str = Query(...)):
    if check_exits_username(username):
        existing_user = users_collection.find_one({"username": username})
        return user_helper(existing_user)
    else:
        return {"message": f"Người dùng {username} không tồn tại"}


@app.post("/login")
def login(request: LoginRequest):
    username = request.username
    password = request.password
    
    if checkLogin(username, password):
        user_username = users_collection.find_one({"username": username}) 
        user_email = users_collection.find_one({"email": username})
        user = user_username if user_username else user_email
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
            
        return {
            "Hello": f"Xin chào {user['username']}",
            "message": message,
            "token": token
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


@app.post("/forgot_password/{email}")
def forgot_password(email: str):
    user = users_collection.find_one({"email":email})
    if user:
        send_reset_password_email(email, user['password'])
        return {"message": f"Password đã gửi về email: {email}"}
    else:
        return {"message": f"Người dùng {email} không tồn tại"}


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



@app.get('/')
async def homepage(request: Request):
    user = request.session.get('user')
    if user:
        username = user.get('name')
        email = user.get('email')
        role = 'User'
        user_iat = user.get('iat')
        
        new_user = {
            'username': username,
            'email': email,
            'gender': "",
            'date':"",
            'number':"",
            'role': role,
            'avatar':"",
            'time_start': user_iat
        }
        update_user = {"$set":{
            'username': username,
            'email': email,
            'role': role,
            'time_start': user_iat
        }}
        
        check_user = users_collection.find_one({"email": email})
        if check_user :
            users_collection.update_one({'email':email}, update_user)
        else:
            users_collection.insert_one(new_user)
        
        print(user_iat)
        current_time = time.time()
        print(current_time)
        if (current_time - user_iat > data['SESSION_TIMEOUT']):
            request.session.pop('user', None)
            return HTMLResponse('<a href="/login">login</a>')
        request.session['last_activity_time'] = time.time()
        data = json.dumps(user)
        html = (
            f'<pre>{data}</pre>'
            '<a href="/logout">logout</a>'
        )
        return HTMLResponse(html)
    return HTMLResponse('<a href="/login_google">login</a>')


@app.get('/login_google')
async def login(request: Request):
    redirect_uri = request.url_for('auth')
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get('/auth')
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f'<h1>{error.error}</h1>')
    user = token.get('userinfo')
    if user:
        request.session['user'] = dict(user)
    return RedirectResponse(url='/')


@app.get('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/')


@app.post('/change_password')
def change_password(username: str, password: ChangePassword):
    pw = password.password
    new_pw1 = password.new1_password
    new_pw2 = password.new2_password
    
    user = users_collection.find_one({"username": username})
    if user:
        if pw == user['password']:
            if new_pw1 == new_pw2:
                value_set = {"$set":{
                    "password": new_pw1
                }}
                users_collection.update_one({"_id": user["_id"]}, value_set)
                return {"message": "Thay đổi mật khẩu thành công!"}
            else:
                return {"message": "Mật khẩu mới chưa trùng khớp!"}
        else:
            return {"message": "Mật khẩu không chính xác!"}
    else:
        return {"message": f"Người dùng {username} không tồn tại"}


@app.post('/update_avatar')
def update_avarta(username: str, avatar: UploadFile = File(...)):
    user = users_collection.find_one({"username": username})
    if user:
        # avatar_data = avatar.read()
        avatar_data = avatar.file.read()
        avatar_base64 = base64.b64encode(avatar_data).decode('utf-8') 
        avatar_set = {"$set":{
            "avatar": avatar_base64
        }}
        users_collection.update_one({"_id": user["_id"]}, avatar_set)
        return {"message": "Avatar cập nhật thành công"}
    else:
        return {"message": f"Người dùng {username} không tồn tại"}


@app.get('/get_avatar/{username}')
def get_avatar(username: str):
    user = users_collection.find_one({"username": username})
    if user and "avatar":
        avatar_base64 = user['avatar']
        avatar_data = base64.b64decode(avatar_base64)
        
        return StreamingResponse(io.BytesIO(avatar_data), media_type="image/png")
    else:
        return {"message": f"Người dùng {username} không tồn tại"}





# Đây là phần của Bình. AE code thì viết lên trên, đừng viết xuống dưới này nhé. Cho dễ tìm :'(


@app.post("/training-file-local")
def api_train_local(file_data: UploadFile, file_config : UploadFile):
    
    best_model_id, best_model, best_score, best_params, model_scores = app_train_local(file_data, file_config)

    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores
    }


@app.post("/training-file-mongodb")
def api_train_mongo():
    data, choose, list_model_search, list_feature, target,matrix,models = get_data_and_config_from_MongoDB()
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_model_search, list_feature, target, matrix, models)

    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores
    }


@app.post("/train-from-requestbody-json/")
def api_train_json(item:Item):
    data, choose, list_model_search, list_feature, target, matrix, models = get_data_config_from_json(item)

    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_model_search, list_feature, target, matrix, models)

    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores
    }
    

if __name__ == "__main__":
    uvicorn.run('app:app', host=data['HOST'], port=data['PORT'], reload=True)
    pass