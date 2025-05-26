from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    Query,
    Depends,
    Response,
    HTTPException,
    status,
)
from typing import List
from io import BytesIO
import pandas as pd
from users.engine import checkLogin
from automl.engine import (
    train_process,
    get_data_and_config_from_MongoDB,
    get_jobs,
    get_one_job,
    push_train_job,
    train_json
)
from automl.model import Item
from users.engine import User
from users.engine import UpdateUser
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
from users.engine import check_exits_email
from users.engine import handleLogin
from users.engine import handle_change_password
from users.engine import handle_update_avatar
from users.engine import handle_get_avatar
from users.engine import handle_signup
from users.engine import handle_delete_user
from users.engine import handle_contact
from users.engine import handle_update_user
import pathlib
from automl.engine import get_config, train_process, get_data_and_config_from_MongoDB
from automl.engine import app_train_local
from fastapi.middleware.cors import CORSMiddleware
from data.uci import get_data_uci_where_id, format_data_automl
from fastapi.responses import JSONResponse
from data.engine import get_list_data, get_data_from_mongodb_by_id, get_one_data, get_user_data_list
from data.engine import upload_data, update_dataset_by_id, delete_dataset_by_id
import threading
from kafka_consumer import run_train_consumer
# default sync
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="!secret")
file_path = "temp.config.yml"
with open(file_path, "r") as f:
    data = yaml.safe_load(f)

config = Config(file_path)
oauth = OAuth(config)

# phương thức để đăng ký một dịch vụ OAuth
CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
oauth.register(
    name="google",
    server_metadata_url=CONF_URL,  # lay thong tin tu may chu
    client_id=data["CLIENT_ID"],
    client_secret=data["CLIENT_SECRET"],
    client_kwargs={
        "scope": "openid email profile",
        "redirect_url": "http://10.100.200.119:9999/auth",
    },
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://10.100.200.119:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    print("Starting Kafka consumer thread...")
    kafka_thread = threading.Thread(target=run_train_consumer, daemon=True)
    kafka_thread.start()
  
@app.get("/")
def read_root():
    return {"message": "FastAPI is running with Kafka consumer"}

@app.get("/home")
def ping():
    return {"AutoML": "version 1.0", "message": "Hi there :P"}


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
        df = pd.read_csv(data, on_bad_lines="skip", sep=sep, engine="python")
        data_list.append(df.values.tolist())
        data.close()
        file.file.close()

    return {"data_list": data_list, "files_list": files_list}


from users.engine import get_current_admin

# Lấy danh sách user
from users.engine import get_list_user
@app.get("/users")
def get_users():
    list_user = get_list_user()
    return list_user


# Lấy 1 user
@app.get("/users/")
def get_user(username: str = Query(...)):
    if check_exits_username(username):
        existing_user = check_exits_username(username)
        return user_helper(existing_user)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại",
        )


@app.post("/login")
def login(request: LoginRequest, response: Response):
    username = request.username
    password = request.password
    user = handleLogin(username, password)
    # response.headers["Authorization"] = f"Bearer {user['token']}"
    return user


# Thêm user, đăng kí user mới
@app.post("/signup")
def singup(new_user: User):
    message = handle_signup(new_user)
    return message


# Xóa user
@app.delete("/delete/{username}")
def delete_user(username):
    message = handle_delete_user(username)
    return message


# update user
@app.put("/update/{username}")
def update_user(username: str, new_user: UpdateUser):
    message = handle_update_user(username, new_user)
    return message


from users.engine import handle_forgot_password


@app.post("/forgot_password/{email}")
def forgot_password(email: str):
    message = handle_forgot_password(email)
    return message


from users.engine import handle_send_otp
from users.engine import handle_verification_email


@app.post("/send_email/{username}")
def send_email(username: str):
    message = handle_send_otp(username)
    return message


@app.post("/verification_email/{username}")
def verification_email(username: str, otp: str):
    message = handle_verification_email(username, otp)
    return message


@app.get("/")
async def homepage(request: Request):
    user = request.session.get("user")
    if user:
        username = user.get("name")
        email = user.get("email")
        role = "User"
        user_iat = user.get("iat")

        new_user = {
            "username": username,
            "email": email,
            "gender": "",
            "date": "",
            "number": "",
            "role": role,
            "avatar": "",
            "time_start": user_iat,
        }
        update_user = {
            "$set": {
                "username": username,
                "email": email,
                "role": role,
                "time_start": user_iat,
            }
        }

        check_user = users_collection.find_one({"email": email})
        if check_user:
            users_collection.update_one({"email": email}, update_user)
        else:
            users_collection.insert_one(new_user)

        print(user_iat)
        current_time = time.time()
        print(current_time)
        if current_time - user_iat > data["SESSION_TIMEOUT"]:
            request.session.pop("user", None)
            return HTMLResponse('<a href="/login">login</a>')
        request.session["last_activity_time"] = time.time()
        data = json.dumps(user)
        html = f"<pre>{data}</pre>" '<a href="/logout">logout</a>'
        return HTMLResponse(html)
    return HTMLResponse('<a href="/login_google">login</a>')


@app.get("/login_google")
async def login(request: Request):
    redirect_uri = request.url_for("auth")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth")
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f"<h1>{error.error}</h1>")
    user = token.get("userinfo")
    if user:
        request.session["user"] = dict(user)
    return RedirectResponse(url="/")


@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")


@app.post("/change_password")
def change_password(username: str, password: ChangePassword):
    pw = password.password
    new_pw1 = password.new1_password
    new_pw2 = password.new2_password
    masage = handle_change_password(username, pw, new_pw1, new_pw2)
    return masage


@app.post("/update_avatar")
def update_avarta(username: str, avatar: UploadFile = File(...)):
    message = handle_update_avatar(username, avatar)
    return message


@app.get("/get_avatar/{username}")
def get_avatar(username: str):
    avatar = handle_get_avatar(username)
    return avatar


@app.post("/contact")
def contact_user(fullname: str = Form(...),
    email: str = Form(...),
    message: str = Form(...)):
    return handle_contact(fullname, email, message)

# Đây là phần của Bình. AE code thì viết lên trên, đừng viết xuống dưới này nhé. Cho dễ tìm :'(


@app.post("/training-file-local")
def api_train_local(file_data: UploadFile, file_config: UploadFile):

    best_model_id, best_model, best_score, best_params, model_scores = app_train_local(
        file_data, file_config
    )

    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores,
    }


@app.post("/training-file-mongodb")
def api_train_mongo():
    data, choose, list_feature, target, metric_list, metric_sort, models = (
        get_data_and_config_from_MongoDB()
    )
    best_model_id, best_model, best_score, best_params, model_scores = train_process(
        data, choose, list_feature, target, metric_list, metric_sort, models
    )

    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_params": best_params,
        "best_score": best_score,
        "orther_model_scores": model_scores,
    }

@app.post("/train-from-requestbody-json/")
def api_train_json(item: Item, userId: str, id_data:str):
    return push_train_job(item, userId, id_data)

@app.post("/get-list-job-by-userId")
def api_get_list_job(user_id: str):
    return get_jobs(user_id)

@app.post("/get-job-info")
def get_job_info(id: str):
    job = get_one_job(id_job=id)
    return job

@app.post("/get-data-from-uci")
def get_data_from_uci(id_data: int):
    df_uci, class_uci = get_data_uci_where_id(id=id_data)
    output = format_data_automl(
        rows=df_uci.values, cols=df_uci.columns.to_list(), class_name=list(class_uci)
    )
    data = {"data": output, "list_feature": df_uci.columns.to_list()}
    return JSONResponse(content=data)


# Lấy danh sách data
@app.post("/get-list-data-by-userid")
def get_list_data_by_userid(id: str):
    list_data = get_list_data(id_user=id)
    return list_data

# Lấy 1 dataset
@app.post("/get-data-info")
def get_data_info(id: str):
    data = get_one_data(id_data=id)
    return data

# Lấy bộ dữ liệu từ mongodb
@app.post("/get-data-from-mongodb-to-train")
def get_data_from_mongodb_to_train(id: str):
    df, class_data = get_data_from_mongodb_by_id(id_data=id)
    output = format_data_automl(
        rows=df.values, cols=df.columns.to_list(), class_name=list(class_data)
    )
    data = {"data": output, "list_feature": df.columns.to_list()}
    return JSONResponse(content=data)

# Upload dataset
@app.post("/upload-dataset")
def upload_dataset(
    user_id: str,
    data_name: str = Form(...),
    data_type: str = Form(...),
    file_data: UploadFile = File(...),
):

    return upload_data(file_data, data_name, data_type, user_id)

# Update dataset
@app.put("/update-dataset/{dataset_id}")
def update_dataset(
    dataset_id: str, data_name: str = Form(None), data_type: str = Form(None), file_data: UploadFile = File(None)
):
    return update_dataset_by_id(dataset_id, data_name, data_type, file_data)

# Delete dataset
@app.delete("/delete-dataset/{dataset_id}")
async def delete_dataset(dataset_id: str):
    return delete_dataset_by_id(dataset_id)

# Lấy danh sách bộ dữ liệu của người dùng cho màn admin
@app.get("/get-list-data-user")
def get_list_data_user():
    list_data = get_user_data_list()
    return list_data

# API push kafka
@app.post("/api-push-kafka")
def api_push_kafka(item: Item, user_id: str, data_id: str):
    return push_train_job(item, user_id, data_id)

if __name__ == "__main__":
    uvicorn.run("app:app", host=data["HOST"], port=data["PORT"], reload=True)
    pass
