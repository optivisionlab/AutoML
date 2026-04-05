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
from bson import ObjectId
from database.database import get_db
from automl.engine import (
    get_jobs,
    get_one_job,
    train_json,
    update_activate_model
)
from automl.model import Item
from users.engine import UpdateUser
from users.engine import user_helper
from users.engine import check_exits_username
from users.engine import send_reset_password_email
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from users.engine import ChangePassword
from users.engine import save_otp, send_otp, generate_otp
import os, uvicorn
from users.engine import check_time_otp
from users.engine import handle_change_password
from users.engine import handle_update_avatar
from users.engine import handle_get_avatar
from users.engine import handle_delete_user
from users.engine import handle_contact
from users.engine import handle_update_user

from automl.engine import app_train_local, inference_model
from fastapi.middleware.cors import CORSMiddleware
from data.uci import get_data_uci_where_id, format_data_automl
from fastapi.responses import JSONResponse
from data.engine import get_list_data, get_one_data, get_all_data
from data.engine import upload_data_to_minio, update_dataset_to_minio_by_id, delete_dataset_at_minio_by_id
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
from users.routers import get_current_user, router as auth
from experiment import exp
from automl.v2.master import master
from hagent.chat_router import router as chat_router
from hagent import chat_store


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
    try:
        await start_producer()
        app.state.kafka_task = asyncio.create_task(kafka_consumer_process(app.state.db))
        app.state.monitor_task = asyncio.create_task(monitor_tasks(app.state.db))
        app.state.kafka_available = True
    except Exception as e:
        print(f"[Server Lifespan] WARNING: Kafka unavailable, skipping: {e}")
        app.state.kafka_task = None
        app.state.monitor_task = None
        app.state.kafka_available = False

    # Tạo index cho OpenClaw chat
    try:
        await chat_store.ensure_indexes(app.state.db)
        print("[Server Lifespan] OpenClaw chat indexes created ✓")
    except Exception as e:
        print(f"[Server Lifespan] WARNING: Failed to create chat indexes: {e}")

    yield # Server Fastapi accepts requests

    print("[Server Lifespan] Shutdown resources...")

    if app.state.kafka_task:
        app.state.kafka_task.cancel()
    if app.state.monitor_task:
        app.state.monitor_task.cancel()
    tasks = [t for t in [app.state.kafka_task, app.state.monitor_task] if t]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await stop_producer()

    # ĐÓNG KẾT NỐI CSDL
    await app.state.client.close()
    print("[Master] Shutdown complete.")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=os.getenv('SUPER_SECRET_KEY', 'secret_key'))
app.include_router(auth)
app.include_router(exp)
app.include_router(master)
app.include_router(chat_router)


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
async def get_users(db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    list_user = await get_list_user(db)
    return list_user


# Lấy 1 user
@app.get("/users/")
async def get_user(username: str = Query(...), db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] == 'user' and current_user['username'] != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    check_username = await check_exits_username(username, db)
    if check_username:
        return user_helper(check_username)

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng {username} không tồn tại",
        )


# Xóa user
@app.delete("/delete/{username}")
async def delete_user(username, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)) -> dict:
    if current_user['role'] == 'user' and current_user['username'] != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    message = await handle_delete_user(username, db)
    return message


# update user
@app.put("/update/{username}")
async def update_user(username: str, new_user: UpdateUser, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] == 'user' and current_user['username'] != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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


@app.post("/change_password")
async def change_password(username: str, password: ChangePassword, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] == 'user' and current_user['username'] != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    current_password = password.current_password
    new_password = password.new_password
    verified_password = password.verified_password
    masage = await handle_change_password(username, current_password, new_password, verified_password, db)
    return masage


@app.post("/update_avatar")
async def update_avarta(username: str, avatar: UploadFile = File(...), db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] == 'user' and current_user['username'] != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    message = await handle_update_avatar(username, avatar, db)
    return message


@app.get("/get_avatar/{username}")
async def get_avatar(username: str, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] == 'user' and current_user['username'] != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    avatar = await handle_get_avatar(username, db)
    return avatar


"""
API chưa sử dụng tới
"""
@app.post("/contact")
async def contact_user(fullname: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    db: AsyncDatabase = Depends(get_db)
):
    return await handle_contact(fullname, email, message, db)


@app.post("/get-list-job-by-userId")
async def api_get_list_job(user_id: str, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['_id'] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )
 
    return await get_jobs(user_id, db)


@app.post("/get-job-info")
async def get_job_info(id: str, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    result = await db.tbl_Job.find_one({"user.id": current_user['_id']})
    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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
async def get_list_data_by_userid(id: str, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['_id'] != id and id != "0":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    list_data = await get_list_data(id_user=id, db=db)
    return list_data


# Lấy 1 dataset
@app.get("/get-data-info")
async def get_data_info(id: str, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    data = await get_one_data(id_data=id, db=db)
    return data


# Upload dataset
@app.post("/upload-dataset")
async def upload_dataset(
    user_id: str,
    data_name: str = Form(...),
    data_type: str = Form(...),
    file_data: UploadFile = File(...),
    db: AsyncDatabase = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if str(current_user['_id']) != str(user_id) and current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

    try:
        dataset = await upload_data_to_minio(file_data, data_name, data_type, user_id, db)
        return dataset
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")


# Update dataset
@app.put("/update-dataset/{dataset_id}")
async def update_dataset(
    dataset_id: str, data_name: str = Form(None), data_type: str = Form(None), file_data: UploadFile = File(None), 
    db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)
):
    exist_data = await db.tbl_Data.find_one({'_id': ObjectId(dataset_id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail="Not found dataset")

    if str(exist_data['userId']) != str(current_user['_id']) and current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission",
        )

    try:
        result = await update_dataset_to_minio_by_id(dataset_id, db, data_name, data_type, file_data)
        return {
            "sucess": result
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")


# Delete dataset
@app.delete("/delete-dataset/{dataset_id}")
async def delete_dataset(dataset_id: str, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    exist_data = await db.tbl_Data.find_one({'_id': ObjectId(dataset_id)})

    if not exist_data:
        raise HTTPException(status_code=404, detail="Not found dataset")

    if str(exist_data['userId']) != str(current_user['_id']) and current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission",
        )
    
    try:
        result = await delete_dataset_at_minio_by_id(dataset_id, db)
        return {
            "success": result
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"{str(e)}")


# Lấy danh sách bộ dữ liệu của người dùng cho màn admin
@app.get("/get-list-data-user")
async def get_list_data_user(db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied",
        )

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
    db: AsyncDatabase = Depends(get_db),
    current_user = Depends(get_current_user)
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
async def api_activate_model(job_id, activate=0, db: AsyncDatabase = Depends(get_db), current_user = Depends(get_current_user)):
    return await update_activate_model(job_id, db, activate)


# ─── OpenClaw: Endpoint danh sách thuật toán ML ─────────

@app.get("/api/v1/available-models/{problem_type}")
async def get_available_models(problem_type: str):
    """
    Trả về danh sách thuật toán ML khả dụng theo loại bài toán.
    Dùng bởi OpenClaw để hiển thị cho người dùng.

    Args:
        problem_type: "classification" hoặc "regression"
    """
    import yaml

    if problem_type not in ("classification", "regression"):
        raise HTTPException(
            status_code=400,
            detail=f"Loại bài toán không hợp lệ: {problem_type}. Chọn 'classification' hoặc 'regression'."
        )

    # Đọc file YAML cấu hình model
    config_path = os.path.join("assets", "system_models", f"{problem_type}.yml")
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail=f"Không tìm thấy cấu hình cho {problem_type}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Trích xuất danh sách model và tham số
    key = f"{problem_type.capitalize()}_models"
    models_data = config.get(key, {})
    metrics = config.get("metric_list", [])

    models = []
    for idx, model_info in models_data.items():
        models.append({
            "index": idx,
            "name": model_info["model"],
            "params": model_info.get("params", []),
        })

    return {
        "problem_type": problem_type,
        "metrics": metrics,
        "models": models,
        "total": len(models),
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host=os.getenv('HOST_BACK_END', '0.0.0.0'), port=int(os.getenv('PORT_BACK_END', 8080)), reload=True)