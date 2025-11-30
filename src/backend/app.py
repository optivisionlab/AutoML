from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    Query,
    Response,
    HTTPException,
    status,
    Depends
)
from pymongo.asynchronous.database import AsyncDatabase
from database.database import get_db
from automl.engine import (
    get_jobs,
    get_one_job,
    train_json,
    update_activate_model
)
from automl.model import Item
from users.engine import User
from users.engine import UpdateUser
from users.engine import user_helper
from users.engine import LoginRequest
from users.engine import create_access_token
from users.engine import check_exits_username
from users.engine import send_reset_password_email
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse, RedirectResponse
from authlib.integrations.starlette_client import OAuth, OAuthError
from users.engine import ChangePassword
from users.engine import save_otp, send_otp, generate_otp
import time, json, os, uvicorn
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

from automl.engine import app_train_local, inference_model
from fastapi.middleware.cors import CORSMiddleware
from data.uci import get_data_uci_where_id, format_data_automl
from fastapi.responses import JSONResponse
from data.engine import get_list_data, get_one_data, get_all_data
from data.engine import upload_data_to_minio, update_dataset_to_minio_by_id, delete_dataset_at_minio_by_id
from users.engine import get_current_admin, get_current_user
from database.database import connection

# Lấy danh sách user
from users.engine import get_list_user
from contextlib import asynccontextmanager
from kafka_consumer import (
    kafka_consumer_process,
    start_producer,
    stop_producer
)
from automl.v2.master import monitor_tasks
import asyncio
from dotenv import load_dotenv


# Load file .env
load_dotenv()

# Lifespan Context Manager 
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context Manager quản lý vòng đời (startup, shutdown) của server
    Trước yield là startup, sau yield là shutdown
    """

    # KẾT NỐI CSDL MONGODB
    app.state.db, app.state.client = await connection()

    # KHỞI TẠO VÀ START PRODUCER 
    await start_producer()

    app.state.kafka_task = asyncio.create_task(kafka_consumer_process(app.state.db))
    app.state.monitor_task = asyncio.create_task(monitor_tasks())

    yield # Server Fastapi accepts requests

    print("[Server Lifespan] Shutdown resources...")

    app.state.kafka_task.cancel()
    app.state.monitor_task.cancel()
    await asyncio.gather(app.state.kafka_task, app.state.monitor_task, return_exceptions=True)
    await stop_producer()

    # ĐÓNG KẾT NỐI CSDL
    await app.state.client.close()
    print("[Master] Shutdown complete.")


# default sync
app = FastAPI(lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key="!secret")
oauth = OAuth()
master_api_url = f"http://{os.getenv('HOST_BACK_END', '0.0.0.0')}:{int(os.getenv('PORT_BACK_END', 8080))}"

# phương thức để đăng ký một dịch vụ OAuth
CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
oauth.register(
    name="google",
    server_metadata_url=CONF_URL,  # lay thong tin tu may chu
    client_id=os.getenv("CLIENT_ID", ""),
    client_secret=os.getenv("CLIENT_SECRET", ""),
    client_kwargs={
        "scope": "openid email profile",
        "redirect_url": f"{master_api_url}/auth",
    },
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {
        "HAutoML": "Open-Source for Automated Machine Learning",
        "Authors": "Đỗ Mạnh Quang, Chử Thị Ánh, Ngọ Công Bình, Bùi Huy Nam, Nguyễn Thị Mỹ Khánh, Nguyễn Thị Minh",
        "Lab": "OptiVisionLab",
        "University": "School of Information and Communications Technology, Hanoi University of Industry"
    }


@app.get("/home")
async def ping():
    return {"AutoML": "version 1.0", "message": "Hi there :P"}


@app.get("/users")
async def get_users(db: AsyncDatabase = Depends(get_db)):
    list_user = await get_list_user(db)
    return list_user


# Lấy 1 user
@app.get("/users/")
async def get_user(username: str = Query(...), db: AsyncDatabase = Depends(get_db)):
    check_username = await check_exits_username(username, db)
    if check_username:
        return user_helper(check_username)

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại",
        )


@app.post("/login")
async def login(request: LoginRequest, response: Response, db: AsyncDatabase = Depends(get_db)):
    username = request.username
    password = request.password
    user = await handleLogin(username, password, db)
    # response.headers["Authorization"] = f"Bearer {user['token']}"
    return user


# Thêm user, đăng kí user mới
@app.post("/signup")
async def singup(new_user: User, db: AsyncDatabase = Depends(get_db)):
    message = await handle_signup(new_user, db)
    return message


# Xóa user
@app.delete("/delete/{username}")
async def delete_user(username, db: AsyncDatabase = Depends(get_db)):
    message = await handle_delete_user(username, db)
    return message


# update user
@app.put("/update/{username}")
async def update_user(username: str, new_user: UpdateUser, db: AsyncDatabase = Depends(get_db)):
    message = await handle_update_user(username, new_user, db)
    return message


from users.engine import handle_forgot_password


@app.post("/forgot_password/{email}")
async def forgot_password(email: str, db: AsyncDatabase = Depends(get_db)):
    message = await handle_forgot_password(email, db)
    return message


from users.engine import handle_send_otp
from users.engine import handle_verification_email


@app.post("/send_email/{username}")
async def send_email(username: str, db: AsyncDatabase = Depends(get_db)):
    message = await handle_send_otp(username, db)
    return message


@app.post("/verification_email/{username}")
async def verification_email(username: str, otp: str, db: AsyncDatabase = Depends(get_db)):
    message = await handle_verification_email(username, otp, db)
    return message


@app.get("/")
async def homepage(request: Request):
    users_collection = request.app.state.db.tbl_User
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

        check_user = await users_collection.find_one({"email": email})
        if check_user:
            await users_collection.update_one({"email": email}, update_user)
        else:
            await users_collection.insert_one(new_user)

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
async def change_password(username: str, password: ChangePassword, db: AsyncDatabase = Depends(get_db)):
    pw = password.password
    new_pw1 = password.new1_password
    new_pw2 = password.new2_password
    masage = await handle_change_password(username, pw, new_pw1, new_pw2, db)
    return masage


@app.post("/update_avatar")
async def update_avarta(username: str, avatar: UploadFile = File(...), db: AsyncDatabase = Depends(get_db)):
    message = await handle_update_avatar(username, avatar, db)
    return message


@app.get("/get_avatar/{username}")
async def get_avatar(username: str, db: AsyncDatabase = Depends(get_db)):
    avatar = await handle_get_avatar(username, db)
    return avatar


@app.post("/contact")
async def contact_user(fullname: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    db: AsyncDatabase = Depends(get_db)
):
    return await handle_contact(fullname, email, message, db)


@app.post("/get-list-job-by-userId")
async def api_get_list_job(user_id: str, db: AsyncDatabase = Depends(get_db)):
    return await get_jobs(user_id, db)

@app.post("/get-job-info")
async def get_job_info(id: str, db: AsyncDatabase = Depends(get_db)):
    return await get_one_job(id_job=id, db=db)

@app.post("/get-data-from-uci")
async def get_data_from_uci(id_data: int):
    df_uci, class_uci = get_data_uci_where_id(id=id_data)
    output = format_data_automl(
        rows=df_uci.values, cols=df_uci.columns.to_list(), class_name=list(class_uci)
    )
    data = {"data": output, "list_feature": df_uci.columns.to_list()}
    return JSONResponse(content=data)


# Lấy danh sách data
@app.post("/get-list-data-by-userid")
async def get_list_data_by_userid(id: str, db: AsyncDatabase = Depends(get_db)):
    list_data = await get_list_data(id_user=id, db=db)
    return list_data


# Lấy 1 dataset
@app.post("/get-data-info")
async def get_data_info(id: str, db: AsyncDatabase = Depends(get_db)):
    data = await get_one_data(id_data=id, db=db)
    return data


# Upload dataset
@app.post("/upload-dataset")
async def upload_dataset(
    user_id: str,
    data_name: str = Form(...),
    data_type: str = Form(...),
    file_data: UploadFile = File(...),
    db: AsyncDatabase = Depends(get_db)
):

    try:
        dataset = await upload_data_to_minio(file_data, data_name, data_type, user_id, db)
        return dataset
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")


# Update dataset
@app.put("/update-dataset/{dataset_id}")
async def update_dataset(
    dataset_id: str, data_name: str = Form(None), data_type: str = Form(None), file_data: UploadFile = File(None), db: AsyncDatabase = Depends(get_db)
):
    try:
        result = await update_dataset_to_minio_by_id(dataset_id, db, data_name, data_type, file_data)
        return {
            "sucess": result
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")


# Delete dataset
@app.delete("/delete-dataset/{dataset_id}")
async def delete_dataset(dataset_id: str, db: AsyncDatabase = Depends(get_db)):
    try:
        result = await delete_dataset_at_minio_by_id(dataset_id, db)
        return {
            "success": result
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")


# Lấy danh sách bộ dữ liệu của người dùng cho màn admin
@app.get("/get-list-data-user")
async def get_list_data_user(db: AsyncDatabase = Depends(get_db)):
    list_data = await get_all_data(db)
    return list_data


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


@app.post("/train-from-requestbody-json/")
def api_train_json(item: Item, userId: str, id_data:str, db: AsyncDatabase = Depends(get_db)):
    return train_json(item, userId, id_data, db)



@app.post("/inference-model")
async def inference(
    job_id: str = Form(...), 
    user_id: str = Form(...),
    file_data: UploadFile = File(...),
    db: AsyncDatabase = Depends(get_db)
):
    try:
        prediction_result = await inference_model(job_id, user_id, file_data, db)

        if isinstance(prediction_result, dict) and "error" in prediction_result:
            raise HTTPException(
                status_code=400, 
                detail=f"Prediction failed: {prediction_result['error']}"
            )
        
        return prediction_result
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"An internal server error occurred: {str(e)}"
        )



@app.post("/activate-model")
def api_activate_model(job_id, activate=0, db: AsyncDatabase = Depends(get_db)):
    return update_activate_model(job_id, db, activate)


from experiment import exp
app.include_router(exp)
    
from automl.v2.master import master
app.include_router(master)

if __name__ == "__main__":
    uvicorn.run("app:app", host=os.getenv('HOST_BACK_END', '0.0.0.0'), port=int(os.getenv('PORT_BACK_END', 8080)), reload=True)