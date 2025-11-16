"""
Ví dụ Code Minh Họa Các Luồng Hệ Thống HAutoML

File này chứa các ví dụ minh họa cách sử dụng các API và luồng xử lý trong HAutoML.
Đây là tài liệu tham khảo, không phải code thực thi.

Tham khảo:
- docs/system-flow-diagram.md: Sơ đồ luồng chi tiết
- .kiro/steering/system-flow.md: Mô tả luồng hệ thống
"""

# ============================================================================
# LUỒNG 1: HUẤN LUYỆN ĐỒNG BỘ (SYNCHRONOUS TRAINING)
# ============================================================================

def example_1_synchronous_training_request():
    """
    Ví dụ request cho huấn luyện đồng bộ
    
    Endpoint: POST /train-from-requestbody-json/
    Mô tả: Client gửi request và chờ kết quả training ngay lập tức
    
    Returns:
        dict: Cấu trúc request body mẫu
    """
    import requests
    
    # Bước 1: Chuẩn bị dữ liệu request
    request_body = {
        "data": [
            {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "species": "setosa"},
            {"sepal_length": 4.9, "sepal_width": 3.0, "petal_length": 1.4, "petal_width": 0.2, "species": "setosa"},
            {"sepal_length": 7.0, "sepal_width": 3.2, "petal_length": 4.7, "petal_width": 1.4, "species": "versicolor"},
            # ... thêm dữ liệu
        ],
        "config": {
            "choose": "new model",  # "new model" hoặc model_id để train lại
            "list_feature": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "target": "species",
            "metric_sort": "accuracy",  # accuracy, precision, recall, f1
            "search_algorithm": "bayesian"  # grid, genetic, bayesian
        }
    }
    
    # Bước 2: Gửi request đến API
    response = requests.post(
        "http://localhost:8000/train-from-requestbody-json/",
        json=request_body,
        params={"userId": "user_id_here", "id_data": "data_id_here"}
    )
    
    # Bước 3: Nhận kết quả
    result = response.json()
    """
    Kết quả trả về:
    {
        "_id": "...",
        "job_id": "uuid-string",
        "best_model_id": 1,
        "best_model": "RandomForestClassifier(...)",
        "best_params": {"n_estimators": 100, "max_depth": 10, ...},
        "best_score": 0.96,
        "orther_model_scores": [
            {
                "model_id": 0,
                "model_name": "DecisionTreeClassifier",
                "best_params": {...},
                "scores": {"accuracy": 0.92, "precision": 0.91, "recall": 0.90, "f1": 0.91}
            },
            ...
        ],
        "config": {...},
        "data": {"id": "...", "name": "iris_dataset"},
        "user": {"id": "...", "name": "username"},
        "create_at": 1234567890.123,
        "status": 1
    }
    """
    return result


def example_1_internal_flow():
    """
    Ví dụ luồng xử lý nội bộ cho training đồng bộ
    
    Mô tả các bước xử lý từ khi nhận request đến khi trả kết quả.
    Code này chỉ mang tính minh họa, tham khảo automl/engine.py cho implementation thực tế.
    """
    # Import giả định (không chạy được, chỉ minh họa)
    from automl.engine import preprocess_data, get_model, training
    from automl.search.factory import SearchStrategyFactory
    import pandas as pd
    
    # Bước 1: Parse request data
    request_data = {...}  # Từ request body
    data = pd.DataFrame(request_data["data"])
    config = request_data["config"]
    
    # Bước 2: Tiền xử lý dữ liệu
    X, y = preprocess_data(
        list_feature=config["list_feature"],
        target=config["target"],
        data=data
    )
    # X: numpy array đã được scaled (StandardScaler)
    # y: numpy array đã được encoded (LabelEncoder)
    
    # Bước 3: Lấy danh sách models và metrics
    models, metric_list = get_model()
    # models: {0: {model: DecisionTreeClassifier(), params: {...}}, 
    #          1: {model: RandomForestClassifier(), params: {...}}, ...}
    # metric_list: ['accuracy', 'precision', 'recall', 'f1']
    
    # Bước 4: Tạo search strategy
    strategy = SearchStrategyFactory.create_strategy(
        config["search_algorithm"],  # 'grid', 'genetic', hoặc 'bayesian'
        {'cv': 5, 'scoring': {...}, 'metric_sort': config["metric_sort"]}
    )
    
    # Bước 5: Training tất cả models
    best_model_id, best_model, best_score, best_params, model_scores = training(
        models=models,
        metric_list=metric_list,
        metric_sort=config["metric_sort"],
        X_train=X,
        y_train=y,
        search_algorithm=config["search_algorithm"]
    )
    
    # Bước 6: Lưu vào MongoDB và trả kết quả
    # (Xem automl/engine.py:train_json() cho chi tiết)
    
    return {
        "best_model_id": best_model_id,
        "best_model": str(best_model),
        "best_score": best_score,
        "best_params": best_params,
        "orther_model_scores": model_scores
    }
    
    # Bước 5: Tạo Search Strategy
    strategy = SearchStrategyFactory.create_strategy(
        algorithm=config["search_algorithm"],
        config={
            'cv': 5,
            'scoring': {'accuracy': make_scorer(accuracy_score)},
            'metric_sort': config["metric_sort"]
        }
    )
    
    # Bước 6: Training từng model
    best_model_id = None
    best_score = -1
    model_results = []
    
    for model_id, model_info in models.items():
        # Tìm siêu tham số tốt nhất
        best_params, best_score_model, _, cv_results = strategy.search(
            model=model_info['model'],
            param_grid=model_info['params'],
            X=X,
            y=y
        )
        
        # Lưu kết quả
        if best_score_model > best_score:
            best_model_id = model_id
            best_score = best_score_model
            best_model = model_info['model'].set_params(**best_params)
            best_model.fit(X, y)
    
    # Bước 7: Lưu vào MongoDB
    model_binary = pickle.dumps(best_model)
    job = {
        "job_id": str(uuid4()),
        "best_model_id": best_model_id,
        "model": model_binary,
        "best_score": best_score,
        "status": 1
    }
    job_collection.insert_one(job)
    
    # Bước 8: Trả kết quả về Client
    return {
        "best_model_id": best_model_id,
        "best_score": best_score,
        "model_scores": model_results
    }


# ============================================================================
# LUỒNG 2: HUẤN LUYỆN BẤT ĐỒNG BỘ (ASYNCHRONOUS TRAINING)
# ============================================================================

def flow_2_asynchronous_training():
    """
    Luồng huấn luyện bất đồng bộ - Client nhận job_id ngay, training chạy background
    Endpoint: POST /v2/auto/jobs/training
    """
    
    # Bước 1: Client gửi request
    request_data = {
        "id_data": "507f1f77bcf86cd799439011",  # MongoDB ObjectId
        "config": {
            "choose": "new model",
            "list_feature": ["feature_0", "feature_1"],
            "target": "target",
            "metric_sort": "f1",
            "search_algorithm": "bayesian"
        }
    }
    
    # Bước 2: API Server tạo job
    job_id = str(uuid4())
    job_doc = {
        "job_id": job_id,
        "item": request_data,
        "status": 0,  # Pending
        "create_at": time.time()
    }
    
    # Bước 3: Lưu job vào MongoDB
    job_collection.insert_one(job_doc)
    
    # Bước 4: Gửi message vào Kafka
    producer.send("train-job-topic", value=job_doc)
    producer.flush()
    
    # Bước 5: Trả job_id ngay lập tức
    return {"job_id": job_id, "status": "pending"}
    
    # === Background Processing ===
    # Kafka Consumer sẽ nhận message và xử lý
    
def kafka_consumer_handler(message):
    """Kafka Consumer xử lý message training"""
    job = message.value
    job_id = job["job_id"]
    
    # Lấy job từ MongoDB
    existing_job = job_collection.find_one({"job_id": job_id})
    
    if existing_job["status"] == 1:
        return  # Đã train rồi
    
    # Thực hiện training (tương tự Luồng 1)
    results = train_process(...)
    
    # Cập nhật job
    job_collection.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": 1,  # Completed
            "best_model": results["best_model"],
            "best_score": results["best_score"]
        }}
    )

def client_check_job_status(job_id):
    """Client kiểm tra trạng thái job"""
    response = requests.get(f"/get-job-info?id={job_id}")
    job = response.json()
    
    if job["status"] == 1:
        print("Training completed!")
        print(f"Best score: {job['best_score']}")
    else:
        print("Training in progress...")


# ============================================================================
# LUỒNG 3: HUẤN LUYỆN PHÂN TÁN (DISTRIBUTED TRAINING)
# ============================================================================

def flow_3_distributed_training():
    """
    Luồng huấn luyện phân tán - Chia models cho nhiều worker
    Endpoint: POST /v2/auto/distributed/mongodb
    """
    
    # Bước 1: Client gửi request
    request_data = {
        "id_data": "507f1f77bcf86cd799439011",
        "config": {
            "choose": "new model",
            "list_feature": ["feature_0", "feature_1", "feature_2"],
            "target": "target",
            "metric_sort": "accuracy",
            "algorithm_search": "genetic"
        }
    }
    
    # Bước 2: Lấy danh sách models
    models = {
        0: {"model": "DecisionTreeClassifier", "params": {...}},
        1: {"model": "RandomForestClassifier", "params": {...}},
        2: {"model": "SVC", "params": {...}},
        3: {"model": "KNeighborsClassifier", "params": {...}},
        4: {"model": "LogisticRegression", "params": {...}},
        5: {"model": "GaussianNB", "params": {...}}
    }
    
    # Bước 3: Chia models cho workers
    n_workers = 3
    models_splits = split_models(models, n_workers)
    # Output:
    # Worker 1: {0: DecisionTree, 1: RandomForest}
    # Worker 2: {0: SVC, 1: KNN}
    # Worker 3: {0: LogisticRegression, 1: GaussianNB}
    
    # Bước 4: Gửi song song đến workers (MAP Phase)
    workers = ["http://localhost:4000", "http://localhost:4001", "http://localhost:4002"]
    
    async def send_to_workers():
        tasks = []
        for worker_url, models_part in zip(workers, models_splits):
            payload = {
                "metrics": ["accuracy", "f1"],
                "models": models_part,
                "id_data": request_data["id_data"],
                "config": request_data["config"]
            }
            task = client.post(f"{worker_url}/train", json=payload)
            tasks.append(task)
        
        # Chờ tất cả workers hoàn thành
        responses = await asyncio.gather(*tasks)
        return responses
    
    worker_responses = await send_to_workers()
    # Output từ mỗi worker:
    # {
    #     "success": True,
    #     "best_model": "base64_encoded_model",
    #     "best_score": 0.95,
    #     "model_scores": [...]
    # }
    
    # Bước 5: REDUCE Phase - Tổng hợp kết quả
    all_model_scores = []
    best_overall_score = -1
    best_model_base64 = None
    
    for response in worker_responses:
        if response["success"]:
            all_model_scores.extend(response["model_scores"])
            
            if response["best_score"] > best_overall_score:
                best_overall_score = response["best_score"]
                best_model_base64 = response["best_model"]
    
    # Decode model
    model_bytes = base64.b64decode(best_model_base64)
    best_model = pickle.loads(model_bytes)
    
    # Bước 6: Lưu kết quả
    job_result = {
        "job_id": str(uuid4()),
        "best_model": str(best_model),
        "model": model_bytes,
        "best_score": best_overall_score,
        "model_scores": all_model_scores
    }
    
    # Lưu vào MongoDB
    job_collection.insert_one(job_result)
    
    # Lưu model vào MinIO
    minIOStorage.put_object(
        bucket_name="models",
        object_name=f"{job_result['job_id']}.pkl",
        data=io.BytesIO(model_bytes)
    )
    
    return job_result


def worker_train_endpoint(request):
    """Worker endpoint xử lý training"""
    payload = request.json()
    
    # Lấy dataset từ MongoDB
    data, features = dataset.get_data_and_features(payload["id_data"])
    
    # Ánh xạ model name sang class
    models = {}
    for id, content in payload["models"].items():
        models[int(id)] = content
        content['model'] = MODEL_MAPPING[content['model']]()
    
    # Training
    _, best_model, best_score, _, model_scores = train_process(
        data=data,
        choose=payload["config"]["choose"],
        list_feature=payload["config"]["list_feature"],
        target=payload["config"]["target"],
        metric_list=payload["metrics"],
        metric_sort=payload["config"]["metric_sort"],
        models=models,
        search_algorithm=payload["config"]["algorithm_search"]
    )
    
    # Serialize model
    model_bytes = pickle.dumps(best_model)
    model_base64 = base64.b64encode(model_bytes).decode('utf-8')
    
    return {
        "success": True,
        "best_model": model_base64,
        "best_score": best_score,
        "model_scores": model_scores
    }


# ============================================================================
# LUỒNG 4: DỰ ĐOÁN VỚI MODEL (INFERENCE)
# ============================================================================

def flow_4_inference():
    """
    Luồng dự đoán với model đã train
    Endpoint: POST /inference-model/
    """
    
    # Bước 1: Client gửi request
    job_id = "550e8400-e29b-41d4-a716-446655440000"
    csv_file = open("test_data.csv", "rb")
    
    # Bước 2: Lấy job từ MongoDB
    job = job_collection.find_one({"job_id": job_id})
    
    # Bước 3: Kiểm tra model đã kích hoạt
    if job.get("activate") != 1:
        return {"error": "model is deactivate"}
    
    # Bước 4: Load model
    model = pickle.loads(job["model"])
    list_feature = job["config"]["list_feature"]
    
    # Bước 5: Đọc và tiền xử lý dữ liệu
    data = pd.read_csv(csv_file)
    
    # Encode categorical features
    for column in data.columns:
        if data[column].dtype == 'object':
            le = LabelEncoder()
            data[column] = le.fit_transform(data[column])
    
    # Lấy features
    X = data[list_feature]
    
    # Bước 6: Dự đoán
    predictions = model.predict(X)
    
    # Bước 7: Thêm kết quả vào dataframe
    data["predict"] = predictions
    
    # Bước 8: Trả kết quả
    return data.to_dict(orient="records")


# ============================================================================
# LUỒNG 5: QUẢN LÝ DATASET
# ============================================================================

def flow_5a_upload_dataset():
    """
    Upload dataset lên hệ thống
    Endpoint: POST /upload-dataset
    """
    
    # Bước 1: Client upload file
    file_data = open("iris.csv", "rb")
    form_data = {
        "user_id": "507f1f77bcf86cd799439011",
        "data_name": "Iris Dataset",
        "data_type": "Classification"
    }
    
    # Bước 2: Lưu file vào MinIO
    bucket_name = "datasets"
    object_name = f"{uuid4()}.csv"
    
    minIOStorage.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=file_data,
        length=file_data.size
    )
    
    # Bước 3: Lưu metadata vào MongoDB
    dataset_doc = {
        "dataName": form_data["data_name"],
        "dataType": form_data["data_type"],
        "user_id": form_data["user_id"],
        "bucket_name": bucket_name,
        "object_name": object_name,
        "created_at": time.time()
    }
    
    result = data_collection.insert_one(dataset_doc)
    dataset_id = str(result.inserted_id)
    
    # Bước 4: Trả kết quả
    return {
        "success": True,
        "dataset_id": dataset_id
    }


def flow_5b_get_dataset():
    """
    Lấy dataset để training
    Endpoint: POST /get-data-from-mongodb-to-train
    """
    
    # Bước 1: Client gửi id_data
    id_data = "507f1f77bcf86cd799439011"
    
    # Bước 2: Lấy metadata từ MongoDB
    dataset = data_collection.find_one({"_id": ObjectId(id_data)})
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    # Bước 3: Lấy file từ MinIO
    file_stream = minIOStorage.get_object(
        bucket_name=dataset["bucket_name"],
        object_name=dataset["object_name"]
    )
    
    # Bước 4: Parse CSV
    df = pd.read_csv(file_stream)
    
    # Bước 5: Format theo chuẩn AutoML
    data_json = df.to_dict(orient="records")
    list_feature = df.columns.tolist()
    
    # Bước 6: Trả kết quả
    return {
        "data": data_json,
        "list_feature": list_feature
    }


# ============================================================================
# LUỒNG 6: XÁC THỰC NGƯỜI DÙNG
# ============================================================================

def flow_6a_login_local():
    """
    Đăng nhập với username/password
    Endpoint: POST /login
    """
    
    # Bước 1: Client gửi credentials
    credentials = {
        "username": "user123",
        "password": "password123"
    }
    
    # Bước 2: Tìm user trong MongoDB
    user = users_collection.find_one({"username": credentials["username"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Bước 3: Verify password
    password_hash = hashlib.sha256(credentials["password"].encode()).hexdigest()
    
    if user["password"] != password_hash:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Bước 4: Tạo JWT token
    token_data = {
        "user_id": str(user["_id"]),
        "username": user["username"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
    
    # Bước 5: Trả token và user info
    return {
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"]
        }
    }


def flow_6b_login_google_oauth():
    """
    Đăng nhập với Google OAuth
    Endpoint: GET /login_google
    """
    
    # Bước 1: Client click "Login with Google"
    # Redirect đến Google OAuth
    redirect_uri = "http://localhost:9999/auth"
    oauth_url = oauth.google.authorize_redirect(redirect_uri)
    
    # Bước 2: Google xác thực user
    # User đăng nhập trên trang Google
    
    # Bước 3: Google callback về /auth
    def auth_callback(request):
        # Lấy token từ Google
        token = oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        
        # Bước 4: Lưu vào session
        request.session["user"] = dict(user_info)
        
        # Bước 5: Lưu/Update user trong MongoDB
        existing_user = users_collection.find_one({"email": user_info["email"]})
        
        if existing_user:
            # Update user
            users_collection.update_one(
                {"email": user_info["email"]},
                {"$set": {
                    "username": user_info["name"],
                    "last_login": time.time()
                }}
            )
        else:
            # Tạo user mới
            new_user = {
                "username": user_info["name"],
                "email": user_info["email"],
                "role": "User",
                "created_at": time.time()
            }
            users_collection.insert_one(new_user)
        
        # Bước 6: Redirect về home
        return RedirectResponse(url="/")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def split_models(models, n_workers):
    """Chia models thành n phần cho workers"""
    model_items = list(models.items())
    splits = [model_items[i::n_workers] for i in range(n_workers)]
    
    result = []
    for split in splits:
        worker_models = {}
        for new_id, (old_id, model_data) in enumerate(split):
            worker_models[new_id] = model_data
        result.append(worker_models)
    
    return result


def preprocess_data(list_feature, target, data):
    """Tiền xử lý dữ liệu"""
    # Encode categorical features
    for column in data.columns:
        if data[column].dtype == 'object':
            le = LabelEncoder()
            data[column] = le.fit_transform(data[column])
    
    # Tách features và target
    X = data[list_feature]
    y = data[target]
    
    # Chuẩn hóa features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, y


# ============================================================================
# MAIN EXECUTION EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("=== HAutoML System Flow Examples ===")
    print("\n1. Synchronous Training")
    print("2. Asynchronous Training")
    print("3. Distributed Training")
    print("4. Inference")
    print("5. Dataset Management")
    print("6. User Authentication")



# ============================================================================
# LUỒNG 2: HUẤN LUYỆN BẤT ĐỒNG BỘ VỚI KAFKA (ASYNCHRONOUS TRAINING)
# ============================================================================

def example_2_async_training_request():
    """
    Ví dụ request cho huấn luyện bất đồng bộ
    
    Endpoint: POST /v2/auto/jobs/training
    Mô tả: Client nhận job_id ngay lập tức, training chạy background qua Kafka
    
    Returns:
        dict: Cấu trúc request và response
    """
    import requests
    import time
    
    # Bước 1: Gửi request training
    request_body = {
        "id_data": "data_id_in_mongodb",  # ID của dataset đã upload
        "config": {
            "choose": "new model",
            "list_feature": ["feature_0", "feature_1", "feature_2"],
            "target": "target_column",
            "metric_sort": "f1",
            "search_algorithm": "genetic"
        }
    }
    
    response = requests.post(
        "http://localhost:8000/v2/auto/jobs/training",
        json=request_body,
        params={"userId": "user_id_here"}
    )
    
    # Bước 2: Nhận job_id ngay lập tức
    result = response.json()
    """
    Response ngay lập tức:
    {
        "_id": "...",
        "job_id": "uuid-string",
        "item": {...},  # Config đã gửi
        "data": {"id": "...", "name": "dataset_name"},
        "user": {"id": "...", "name": "username"},
        "status": 0,  # 0 = pending, 1 = completed
        "activate": 0,
        "create_at": 1234567890.123
    }
    """
    job_id = result["job_id"]
    
    # Bước 3: Polling để kiểm tra kết quả
    while True:
        check_response = requests.get(
            f"http://localhost:8000/get-job-info",
            params={"id": job_id}
        )
        job_status = check_response.json()
        
        if job_status["status"] == 1:  # Completed
            print("Training hoàn tất!")
            print(f"Best model: {job_status['best_model']}")
            print(f"Best score: {job_status['best_score']}")
            break
        
        print("Training đang chạy...")
        time.sleep(5)  # Chờ 5 giây trước khi check lại
    
    return job_status


def example_2_kafka_flow():
    """
    Ví dụ luồng xử lý Kafka consumer
    
    Mô tả: Kafka consumer lắng nghe topic và xử lý training job
    Tham khảo: kafka_consumer.py
    """
    from kafka import KafkaConsumer
    from automl.engine import train_json_from_job
    import json
    
    # Bước 1: Khởi tạo Kafka consumer
    consumer = KafkaConsumer(
        'train-job-topic',
        bootstrap_servers=['localhost:9092'],
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    # Bước 2: Lắng nghe messages
    for message in consumer:
        job_data = message.value
        """
        job_data structure:
        {
            "job_id": "uuid-string",
            "item": {
                "data": [...],
                "config": {...}
            },
            "data": {"id": "...", "name": "..."},
            "user": {"id": "...", "name": "..."},
            "status": 0
        }
        """
        
        # Bước 3: Xử lý training
        print(f"Nhận job: {job_data['job_id']}")
        result = train_json_from_job(job_data)
        print(f"Hoàn tất job: {job_data['job_id']}")


# ============================================================================
# LUỒNG 3: HUẤN LUYỆN PHÂN TÁN (DISTRIBUTED TRAINING)
# ============================================================================

def example_3_distributed_training_request():
    """
    Ví dụ request cho huấn luyện phân tán
    
    Endpoint: POST /v2/auto/distributed/mongodb
    Mô tả: Training được chia đều cho nhiều worker nodes (MapReduce)
    
    Returns:
        dict: Kết quả training từ nhiều workers
    """
    import requests
    
    # Bước 1: Gửi request
    request_body = {
        "id_data": "data_id_in_mongodb",
        "config": {
            "choose": "new model",
            "list_feature": ["feature_0", "feature_1", "feature_2", "feature_3"],
            "target": "target_column",
            "metric_sort": "accuracy",
            "search_algorithm": "bayesian"
        }
    }
    
    response = requests.post(
        "http://localhost:8000/v2/auto/distributed/mongodb",
        json=request_body,
        params={"userId": "user_id_here"}
    )
    
    # Bước 2: Nhận kết quả đã được reduce từ tất cả workers
    result = response.json()
    """
    Response:
    {
        "job_id": "uuid-string",
        "best_model_id": 2,
        "best_model": "SVC(...)",
        "best_score": 0.97,
        "best_params": {"C": 1.0, "kernel": "rbf", ...},
        "orther_model_scores": [
            # Kết quả từ tất cả workers đã được gộp lại
            {"model_id": 0, "model_name": "DecisionTree", ...},
            {"model_id": 1, "model_name": "RandomForest", ...},
            {"model_id": 2, "model_name": "SVC", ...},
            ...
        ]
    }
    """
    return result


def example_3_mapreduce_flow():
    """
    Ví dụ luồng MapReduce cho distributed training
    
    Mô tả: Coordinator chia models cho workers, sau đó reduce kết quả
    Tham khảo: automl/v2/distributed.py
    """
    import asyncio
    import httpx
    
    async def map_phase(models, n_workers=3):
        """
        MAP Phase: Chia models cho workers
        
        Giả sử có 6 models và 3 workers:
        - Worker 1: models 0, 1
        - Worker 2: models 2, 3
        - Worker 3: models 4, 5
        """
        # Chia models
        models_per_worker = len(models) // n_workers
        tasks = []
        
        for i in range(n_workers):
            start_idx = i * models_per_worker
            end_idx = start_idx + models_per_worker if i < n_workers - 1 else len(models)
            models_part = models[start_idx:end_idx]
            
            # Gửi đến worker
            worker_url = f"http://localhost:{4000 + i}/train"
            task = send_to_worker(worker_url, models_part)
            tasks.append(task)
        
        # Chờ tất cả workers hoàn tất
        results = await asyncio.gather(*tasks)
        return results
    
    async def send_to_worker(worker_url, models_part):
        """Gửi models_part đến một worker"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                worker_url,
                json={
                    "models": models_part,
                    "id_data": "data_id",
                    "config": {...}
                }
            )
            return response.json()
    
    def reduce_phase(worker_results):
        """
        REDUCE Phase: Gộp kết quả từ tất cả workers
        
        Args:
            worker_results: List of results from workers
            
        Returns:
            dict: Best model và tất cả model scores
        """
        all_model_scores = []
        best_score = -1
        best_model = None
        best_params = None
        
        # Gộp kết quả
        for result in worker_results:
            all_model_scores.extend(result["model_scores"])
            
            if result["best_score"] > best_score:
                best_score = result["best_score"]
                best_model = result["best_model"]
                best_params = result["best_params"]
        
        return {
            "best_model": best_model,
            "best_score": best_score,
            "best_params": best_params,
            "orther_model_scores": all_model_scores
        }


# ============================================================================
# LUỒNG 4: DỰ ĐOÁN VỚI MODEL (INFERENCE)
# ============================================================================

def example_4_inference_request():
    """
    Ví dụ request cho inference
    
    Endpoint: POST /inference-model/
    Mô tả: Sử dụng model đã train để dự đoán dữ liệu mới
    
    Returns:
        list: Dữ liệu với cột predictions
    """
    import requests
    
    # Bước 1: Chuẩn bị file dữ liệu cần dự đoán
    # File CSV với các features giống lúc training
    files = {
        'file_data': open('new_data.csv', 'rb')
    }
    
    # Bước 2: Gửi request
    response = requests.post(
        "http://localhost:8000/inference-model/",
        files=files,
        params={"job_id": "job_id_from_training"}
    )
    
    # Bước 3: Nhận predictions
    predictions = response.json()
    """
    Response:
    [
        {"feature_0": 5.1, "feature_1": 3.5, ..., "predict": "setosa"},
        {"feature_0": 6.2, "feature_1": 2.9, ..., "predict": "versicolor"},
        ...
    ]
    """
    return predictions


def example_4_inference_flow():
    """
    Ví dụ luồng xử lý inference
    
    Mô tả: Load model từ MongoDB và thực hiện prediction
    Tham khảo: automl/engine.py:inference_model()
    """
    import pickle
    import pandas as pd
    from sklearn.preprocessing import LabelEncoder
    from database.database import get_database
    
    # Bước 1: Lấy model từ MongoDB
    db = get_database()
    job_collection = db["tbl_Job"]
    
    job_id = "job_id_here"
    stored_job = job_collection.find_one({"job_id": job_id})
    
    # Bước 2: Kiểm tra model đã được activate
    if stored_job.get("activate") != 1:
        return {"error": "Model chưa được kích hoạt"}
    
    # Bước 3: Deserialize model
    model = pickle.loads(stored_job["model"])
    list_feature = stored_job["config"]["list_feature"]
    
    # Bước 4: Chuẩn bị dữ liệu mới
    new_data = pd.read_csv("new_data.csv")
    
    # Encode categorical features (giống lúc training)
    for column in new_data.columns:
        if new_data[column].dtype == 'object':
            le = LabelEncoder()
            new_data[column] = le.fit_transform(new_data[column])
    
    # Lấy features
    X = new_data[list_feature]
    
    # Bước 5: Dự đoán
    predictions = model.predict(X)
    new_data["predict"] = predictions
    
    # Bước 6: Trả kết quả
    return new_data.to_dict(orient="records")


# ============================================================================
# LUỒNG 5: QUẢN LÝ DATASET
# ============================================================================

def example_5_upload_dataset():
    """
    Ví dụ upload dataset lên MinIO
    
    Endpoint: POST /upload-dataset
    Mô tả: Upload CSV file và lưu metadata vào MongoDB
    
    Returns:
        dict: Dataset ID và thông tin
    """
    import requests
    
    # Bước 1: Chuẩn bị file
    files = {
        'file_data': open('iris.csv', 'rb')
    }
    
    data = {
        'user_id': 'user_id_here',
        'data_name': 'Iris Dataset',
        'data_type': 'classification'
    }
    
    # Bước 2: Upload
    response = requests.post(
        "http://localhost:8000/upload-dataset",
        files=files,
        data=data
    )
    
    result = response.json()
    """
    Response:
    {
        "success": true,
        "dataset_id": "mongodb_object_id",
        "message": "Upload thành công"
    }
    """
    return result


def example_5_get_dataset():
    """
    Ví dụ lấy dataset từ MongoDB/MinIO
    
    Endpoint: POST /get-data-from-mongodb-to-train
    Mô tả: Lấy dataset đã upload để sử dụng cho training
    
    Returns:
        dict: Dataset và list features
    """
    import requests
    
    # Bước 1: Request dataset
    response = requests.post(
        "http://localhost:8000/get-data-from-mongodb-to-train",
        json={"id_data": "dataset_id_here"}
    )
    
    result = response.json()
    """
    Response:
    {
        "data": [
            {"feature_0": 5.1, "feature_1": 3.5, "target": "setosa"},
            ...
        ],
        "list_feature": ["feature_0", "feature_1", "feature_2", "feature_3"],
        "target": "target"
    }
    """
    return result


# ============================================================================
# LUỒNG 6: SO SÁNH CÁC SEARCH ALGORITHMS
# ============================================================================

def example_6_compare_search_algorithms():
    """
    Ví dụ so sánh hiệu suất của các thuật toán tìm kiếm
    
    Mô tả: Grid Search vs Genetic Algorithm vs Bayesian Search
    """
    import time
    
    algorithms = ["grid", "genetic", "bayesian"]
    results = {}
    
    for algo in algorithms:
        print(f"\n{'='*60}")
        print(f"Testing {algo.upper()} Search")
        print(f"{'='*60}")
        
        request_body = {
            "data": [...],  # Same dataset
            "config": {
                "choose": "new model",
                "list_feature": ["feature_0", "feature_1", "feature_2", "feature_3"],
                "target": "target",
                "metric_sort": "accuracy",
                "search_algorithm": algo
            }
        }
        
        start_time = time.time()
        # response = requests.post(..., json=request_body)
        # result = response.json()
        end_time = time.time()
        
        results[algo] = {
            "duration": end_time - start_time,
            # "best_score": result["best_score"],
            # "best_params": result["best_params"]
        }
    
    """
    Kết quả mong đợi:
    
    Grid Search:
    - Thời gian: Lâu nhất (thử tất cả combinations)
    - Độ chính xác: Cao nhất (tìm kiếm toàn diện)
    - Phù hợp: Không gian tham số nhỏ
    
    Genetic Algorithm:
    - Thời gian: Nhanh (evolution-based)
    - Độ chính xác: Tốt (có thể bỏ sót optimal)
    - Phù hợp: Không gian tham số lớn, cần kết quả nhanh
    
    Bayesian Search:
    - Thời gian: Trung bình (intelligent sampling)
    - Độ chính xác: Rất tốt (học từ iterations trước)
    - Phù hợp: Cân bằng giữa tốc độ và độ chính xác
    """
    
    return results


# ============================================================================
# BEST PRACTICES VÀ LƯU Ý
# ============================================================================

"""
BEST PRACTICES:

1. Chọn Search Algorithm:
   - Grid Search: Dataset nhỏ, cần kết quả tối ưu nhất
   - Genetic Algorithm: Dataset lớn, cần kết quả nhanh
   - Bayesian Search: Cân bằng tốc độ và độ chính xác (RECOMMENDED)

2. Metric Selection:
   - Balanced dataset: accuracy hoặc f1
   - Imbalanced dataset: precision, recall, hoặc f1 (weighted)
   - Multi-class: macro averaging

3. Feature Engineering:
   - Luôn chuẩn hóa numerical features (StandardScaler)
   - Encode categorical features (LabelEncoder)
   - Xử lý missing values trước khi training

4. Model Activation:
   - Chỉ activate model sau khi đã test kỹ
   - Có thể có nhiều models trained nhưng chỉ 1 active
   - Sử dụng endpoint /update-activate-model để quản lý

5. Error Handling:
   - Luôn kiểm tra response status code
   - Xử lý timeout cho async training
   - Validate input data trước khi gửi request

6. Performance:
   - Sử dụng distributed training cho dataset lớn
   - Cache dataset đã upload để tái sử dụng
   - Monitor worker health với /health endpoint
"""
