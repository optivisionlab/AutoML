/**
 * Dedicated English Markdown content for sub-topics in HAutoML documentation.
 * Ensures every single sidebar navigation item has comprehensive, detailed data in English.
 */

export const FIRST_TRAINING_MD_EN = `# First Model Training Guide

This guide takes you step-by-step from data preparation to successfully training your first Automated Machine Learning model with **HAutoML**, evaluating model leaderboards, and running real-time inference.

---

## 🎯 Learning Objectives
- Master the End-to-End AutoML workflow within the HAutoML user interface.
- Upload tabular datasets and define appropriate ML task configurations.
- Configure hyperparameter search spaces and monitor real-time training progress via Kafka Workers.
- Analyze evaluation leaderboards and test live predictions on unseen test records.

---

## 📋 Step 1: Prepare Your Tabular Dataset

HAutoML natively supports standard tabular file formats: **CSV (.csv)**, **Excel (.xlsx)**, and **JSON (.json)**.

> [!TIP]
> You can also explore built-in benchmark datasets (such as **Iris Flower**, **Titanic Survival**, **Wine Quality**, or **California Housing**) to test the pipeline immediately without manual uploads.

**Input Data Conventions:**
1. **Header Row**: Must specify clear feature column names.
2. **Target Column**: Must contain the target label to predict (e.g., \`species\` for classification or \`price\` for regression).
3. **Missing Values**: No manual cleaning or imputation is needed; HAutoML automatically detects and imputes missing fields intelligently.

---

## 🚀 Step 2: Upload Dataset to HAutoML

1. Log into HAutoML using your credentials or **Google OAuth 2.0**.
2. Navigate to **"My Datasets"** (\`/my-datasets\`) from the main menu.
3. Click the **"Upload Dataset"** button:
   - **Dataset Name**: Provide a descriptive title (e.g., \`Iris Flower Classification\`).
   - **Task Type**: Select \`Classification\` or \`Regression\`.
   - **File**: Drag and drop your CSV file into the upload zone.
4. Click **Confirm Upload**. The file is securely stored in **MinIO Object Storage**, and a 10-row dataset preview with schema summary appears.

---

## ⚙️ Step 3: Configure Training Wizard

Click the **"Train Model"** button next to your dataset to open the interactive setup wizard:

### 1. Select Target Column
- Select the column you want the machine learning model to predict (e.g., \`species\`).

### 2. Feature Selection
- By default, all remaining columns are selected as input features.
- Uncheck non-predictive identifiers (such as record IDs, student IDs, or names).

### 3. Algorithm Selection
- **Classification**: Random Forest, Logistic Regression, LightGBM, Support Vector Machine (SVM), Decision Tree, K-Nearest Neighbors.
- **Regression**: Random Forest Regressor, Linear Regression, Ridge, Lasso, Gradient Boosting.
- *Recommended*: Keep **"Auto (All Algorithms)"** so HAutoML evaluates and ranks all candidates.

### 4. Hyperparameter Optimization (HPO) Strategy
- **Search Method**: Select \`Bayesian Optimization\` or \`Random Search\`.
- **Primary Metric**: Choose \`F1-Score\` or \`Accuracy\` for classification; \`RMSE\` or \`R²\` for regression.
- **Cross-Validation**: Defaults to $k=5$ fold CV to prevent overfitting.

---

## ⚡ Step 4: Launch & Monitor Progress

1. Click **"Submit Training Job"**.
2. A unique \`job_id\` is created and dispatched into the **Apache Kafka** queue.
3. Background **Worker** nodes consume the job and execute training in parallel.
4. Track real-time progress on the **Training History** page (\`/training-history\`):
   - Job lifecycle states: \`Queued\` ➔ \`Processing\` ➔ \`Completed\`.
   - Real-time training logs per algorithm and fold.

---

## 📊 Step 5: Leaderboard Analysis & Metrics

Once complete:
1. **Model Leaderboard**: Inspect models ranked by your chosen optimization metric. The top performer is awarded the **Best Model** badge.
2. **In-depth Metrics**:
   - **Confusion Matrix**.
   - **Classification Report**: Precision, Recall, F1-Score per class.
   - **Feature Importance**: Bar chart displaying relative feature contributions.
   - **Optimal Hyperparameters**: Discovered optimal parameter values.

---

## 🔮 Step 6: Activate & Test Live Inference

1. Click **"Activate Model"** to deploy the selected model as your active serving endpoint.
2. Switch to the **"Playground"** tab:
   - Enter feature inputs into the form.
   - Click **"Predict"** to receive instantaneous predictions along with confidence probabilities.
3. Call the \`POST /inference-model/\` REST API endpoint to integrate predictions into external production software.
`;

export const DISTRIBUTED_COMPUTING_MD_EN = `# Distributed Computing & Worker Architecture

HAutoML v2.2 is engineered with a modern distributed microservices architecture, decoupling the API Gateway from compute-intensive machine learning workloads through Apache Kafka message streaming and MinIO S3 object storage.

---

## 🏗️ Master - Worker Architecture

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                   HAutoML Master / API                      │
│                  (FastAPI Backend Service)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
            Task Dispatch      │  Kafka Message Stream
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Apache Kafka Message Broker                 │
│              Topic: 'automl_training_tasks'                 │
└───────┬──────────────────────┬──────────────────────┬───────┘
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Worker 1   │       │   Worker 2   │       │   Worker N   │
│  (Node Alpha)│       │  (Node Beta) │       │ (Auto-scale) │
└───────┬──────┘       └───────┬──────┘       └───────┬──────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
        ┌─────────────────────────────────────────────┐
        │        MinIO Object Storage & MongoDB       │
        │      (Stores Models, Artifacts & Logs)      │
        └─────────────────────────────────────────────┘
\`\`\`

---

## ⚙️ Core Architecture Layers

### 1. Master Service (API Server)
- **Framework**: FastAPI (Python 3.11).
- **Responsibilities**:
  - Ingests REST training requests from clients.
  - Validates dataset schemas and user hyperparameter bounds.
  - Creates the tracking job entry in MongoDB.
  - Publishes task payloads into Kafka topics.

### 2. Message Broker (Apache Kafka)
- Guarantees high-throughput queuing with zero data loss.
- **Key Topics**:
  - \`automl_training_tasks\`: Pending training workloads waiting for worker pick-up.
  - \`automl_status_updates\`: Real-time percentage progress and metric updates streamed back to Master.

### 3. Worker Cluster
- Independent Python consumer daemons.
- Can run locally, across bare-metal server clusters, or across GPU-accelerated cloud nodes:
  - Fetches raw datasets from MinIO into memory buffers.
  - Executes preprocessing pipelines and AutoML model fitting (Scikit-Learn, LightGBM, XGBoost).
  - Performs multi-fold parallel cross-validation.
  - Uploads serialized artifacts (\`.pkl\`, \`.joblib\`) to MinIO.
  - Commits completion statuses to MongoDB.

---

## 📈 Horizontal Worker Scaling

You can scale worker capacity elastically without restarting the backend API:

### Scaling via Docker Compose
\`\`\`bash
# Scale worker cluster to 4 concurrent containers
docker-compose up -d --scale worker=4
\`\`\`

### Running Remote Workers on External Nodes
\`\`\`bash
# Run standalone worker connecting to central Kafka and MinIO
python -m cluster.worker \\
  --kafka-server 192.168.1.100:9092 \\
  --minio-endpoint 192.168.1.100:9000 \\
  --mongodb-connect mongodb://192.168.1.100:27017
\`\`\`

---

## 🛡️ Fault Tolerance & Snoozing

- **Task Timeout (\`TASK_TIMEOUT_SECONDS\`)**: Defaults to 1800 seconds. If a worker hangs or crashes mid-training, the master reclaims the task.
- **Task Snoozes & Retries (\`MAX_TASK_SNOOZES\`)**: Uncommitted Kafka offsets are automatically redistributed to healthy workers (up to 3 retry attempts).
- **Stateless Storage**: Artifacts and datasets reside in MinIO, allowing any worker in the cluster to access required files immediately.
`;

export const HPO_TUNING_MD_EN = `# Hyperparameter Optimization (HPO) & Model Tuning

Hyperparameter Optimization (HPO) is a core scientific engine in HAutoML, determining optimal hyperparameter configurations to maximize model generalization and predictive accuracy.

---

## 🔍 Hyperparameter Search Space

Each machine learning algorithm exposes characteristic hyperparameter bounds:
- **Random Forest**:
  - \`n_estimators\`: Number of ensemble decision trees ($[10, 50, 100, 200]$).
  - \`max_depth\`: Tree maximum depth ($[3, 5, 10, \\text{None}]$).
  - \`min_samples_split\`: Minimum samples needed to split an internal node ($[2, 5, 10]$).
  - \`criterion\`: Quality criterion (\`gini\`, \`entropy\`, \`log_loss\`).
- **LightGBM / Gradient Boosting**:
  - \`learning_rate\`: Shrinkage rate ($\\eta \\in [0.01, 0.2]$).
  - \`num_leaves\`: Maximum tree leaves ($[15, 31, 63]$).
  - \`subsample\`: Row subsample ratio ($[0.6, 0.8, 1.0]$).
- **Support Vector Machine (SVM)**:
  - \`C\`: Regularization margin penalty ($[0.1, 1, 10, 100]$).
  - \`kernel\`: Transformation kernel (\`linear\`, \`rbf\`, \`poly\`).
  - \`gamma\`: Kernel coefficient for RBF/Poly.

---

## 🧠 Supported Search Strategies

### 1. Grid Search
- Exhaustively evaluates all Cartesian coordinate combinations across specified grids.
- **Pros**: Guaranteed optimal candidate within discrete grid.
- **Cons**: Exponential computational cost ($O(k^d)$).

### 2. Random Search
- Randomly samples $N$ configurations from continuous/discrete parameter distributions.
- **Pros**: Bergstra & Bengio (2012) proved Random Search discovers near-optimal points dramatically faster than Grid Search across high-dimensional search spaces.

### 3. Bayesian Optimization (Recommended)
- Fits probabilistic surrogate models (Gaussian Process / Tree-structured Parzen Estimator) over past evaluation histories:
$$\\theta^* = \\arg\\max_{\\theta \\in \\Theta} \\mathbb{E}[f(\\theta)]$$
- Intelligently balances:
  - **Exploitation**: Samples regions that yielded superior scores in past trials.
  - **Exploration**: Evaluates uncertain parameter regions to avoid local optima.

### 4. Genetic Algorithm (GA - v2.1+)
- Encodes parameter candidate sets into chromosome individuals.
- Simulates natural selection through fitness scoring, crossover recombination, and mutations over successive generations.

---

## 🛡️ k-Fold Cross-Validation

To prevent test set leakage and overfitting, HAutoML enforces $k$-fold cross-validation ($k=5$):

$$\\text{CV Score} = \\frac{1}{k} \\sum_{i=1}^{k} \\mathcal{M}\\left(f_\\theta(D_{\\text{train}}^{(i)}), D_{\\text{val}}^{(i)}\\right)$$

- Stratified splitting guarantees proportional target class distribution across folds.
- Preprocessing steps (imputation, scaling, one-hot encoding) are fitted strictly on each fold's training slice.
`;

export const EVALUATION_METRICS_MD_EN = `# Model Evaluation Metrics & Scoring Criteria

HAutoML computes a comprehensive suite of statistical metrics across both Classification and Regression tasks. The platform continuously recalculates these criteria during hyperparameter search to rank and select the Best Model.

---

## 📊 1. Classification Metrics

Based on the Confusion Matrix:
- **TP (True Positive)**: Correctly predicted positive instances.
- **TN (True Negative)**: Correctly predicted negative instances.
- **FP (False Positive)**: Type I Error (negative instance predicted as positive).
- **FN (False Negative)**: Type II Error (positive instance predicted as negative).

### A. Accuracy
Ratio of correct predictions over total predictions:
$$\\text{Accuracy} = \\frac{TP + TN}{TP + TN + FP + FN}$$
> [!NOTE]
> Best suited for balanced target distributions.

### B. Precision
Percentage of positive predictions that are truly positive:
$$\\text{Precision} = \\frac{TP}{TP + FP}$$
*Use Case*: Fraud detection, spam filtering (where false alarms carry high operational costs).

### C. Recall (Sensitivity)
Percentage of actual positive instances correctly identified:
$$\\text{Recall} = \\frac{TP}{TP + FN}$$
*Use Case*: Medical diagnostics (where missing positive cases carries catastrophic consequences).

### D. F1-Score
Harmonic mean of Precision and Recall:
$$\\text{F1} = 2 \\times \\frac{\\text{Precision} \\times \\text{Recall}}{\\text{Precision} + \\text{Recall}} = \\frac{2TP}{2TP + FP + FN}$$

### E. Balanced Accuracy
Macro-average of recalls across all individual classes, ideal for heavily imbalanced datasets:
$$\\text{Balanced Accuracy} = \\frac{1}{K} \\sum_{i=1}^{K} \\frac{TP_i}{TP_i + FN_i}$$

### F. ROC-AUC
Area under the Receiver Operating Characteristic curve. Measures discriminatory ability between classes across all decision thresholds.

---

## 📈 2. Regression Metrics

Where $y_i$ is ground truth, $\\hat{y}_i$ is predicted value, and $\\bar{y}$ is mean target:

### A. MAE (Mean Absolute Error)
Average magnitude of errors:
$$\\text{MAE} = \\frac{1}{n} \\sum_{i=1}^{n} |y_i - \\hat{y}_i|$$
- Preserves native units of the target variable.
- Robust against outlier contamination.

### B. MSE & RMSE (Root Mean Squared Error)
$$\\text{MSE} = \\frac{1}{n} \\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2 \\quad \\Longrightarrow \\quad \\text{RMSE} = \\sqrt{\\text{MSE}}$$
- Heavily penalizes large deviation errors.
- Industry standard for continuous pricing and demand forecasting.

### C. $R^2$ Score (Coefficient of Determination)
Proportion of variance explained by model predictors:
$$R^2 = 1 - \\frac{\\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2}{\\sum_{i=1}^{n} (y_i - \\bar{y})^2}$$
- $R^2 = 1.0$: Flawless prediction with zero residual variance.
- $R^2 = 0.0$: Explains no more than baseline average prediction.
- $R^2 < 0.0$: Model performs worse than horizontal mean line.
`;

export const API_AUTH_MD_EN = `# API Reference: User Management & Authentication (Auth API)

Comprehensive documentation for endpoints handling registration, authentication, JWT Bearer Token issuance, and profile management in HAutoML.

---

## 🌐 Base URL
\`\`\`
http://localhost:8000
\`\`\`

Authenticated requests must supply the HTTP Authorization header:
\`\`\`http
Authorization: Bearer <access_token>
\`\`\`

---

## 📌 Endpoints

### 1. User Registration (\`POST /signup\`)
Registers a new user account.

- **URL**: \`/signup\`
- **Method**: \`POST\`
- **Request Body (JSON)**:
\`\`\`json
{
  "username": "vietanh",
  "email": "vietanh@example.com",
  "password": "SecurePassword123!",
  "fullName": "Hoang Viet Anh"
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "message": "User registered successfully",
  "userId": "66123456789abcdef"
}
\`\`\`

---

### 2. User Login (\`POST /login\`)
Authenticates credentials and issues a JWT Bearer Token.

- **URL**: \`/login\`
- **Method**: \`POST\`
- **Request Body (JSON)**:
\`\`\`json
{
  "username": "vietanh",
  "password": "SecurePassword123!"
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 1440,
  "user": {
    "id": "66123456789abcdef",
    "username": "vietanh",
    "email": "vietanh@example.com",
    "role": "user"
  }
}
\`\`\`

---

### 3. Get User Profile (\`GET /users/\`)
- **URL**: \`/users/?username={username}\`
- **Method**: \`GET\`
- **Response (200 OK)**:
\`\`\`json
{
  "id": "66123456789abcdef",
  "username": "vietanh",
  "email": "vietanh@example.com",
  "createdAt": "2026-01-15T08:30:00Z"
}
\`\`\`

---

### 4. Change Password (\`POST /change_password\`)
- **URL**: \`/change_password?username={username}\`
- **Method**: \`POST\`
- **Request Body**:
\`\`\`json
{
  "password": "OldPassword123!",
  "new1_password": "NewSecurePassword456!",
  "new2_password": "NewSecurePassword456!"
}
\`\`\`

---

### 5. Google OAuth 2.0 Integration
- \`GET /login_google\`: Redirects user to Google OAuth Consent screen.
- \`GET /auth\`: Callback URL receiving Google verification code and establishing session.
`;

export const API_DATASETS_MD_EN = `# API Reference: Dataset Management (Dataset API)

REST endpoints for uploading, querying, inspecting metadata, and managing tabular datasets stored in MinIO S3 storage.

---

## 🌐 Base URL
\`\`\`
http://localhost:8000
\`\`\`

---

## 📌 Endpoints

### 1. Upload Dataset (\`POST /upload-dataset\`)
Uploads a dataset file and persists it to MinIO Object Storage.

- **URL**: \`/upload-dataset\`
- **Method**: \`POST\`
- **Content-Type**: \`multipart/form-data\`
- **Form Fields**:
  - \`user_id\` (string, required): Owner user ID.
  - \`data_name\` (string, required): Dataset display name.
  - \`data_type\` (string, required): \`classification\` or \`regression\`.
  - \`file_data\` (file, required): File payload (\`.csv\`, \`.xlsx\`, \`.json\`).
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "dataset_id": "data_987654321",
  "data_name": "Iris Flower",
  "rows": 150,
  "columns": 5,
  "file_url": "minio/datasets/66123456789abcdef/data_987654321.csv"
}
\`\`\`

---

### 2. List User Datasets (\`POST /get-list-data-by-userid\`)
- **URL**: \`/get-list-data-by-userid\`
- **Method**: \`POST\`
- **Request Body**: \`{"id": "66123456789abcdef"}\`
- **Response (200 OK)**:
\`\`\`json
[
  {
    "id": "data_987654321",
    "name": "Iris Flower Dataset",
    "dataType": "classification",
    "rowCount": 150,
    "columnCount": 5,
    "createdAt": "2026-03-10T14:20:00Z"
  }
]
\`\`\`

---

### 3. Inspect Dataset Metadata (\`POST /get-data-info\`)
- **URL**: \`/get-data-info\`
- **Method**: \`POST\`
- **Request Body**: \`{"id": "data_987654321"}\`
- **Response (200 OK)**:
\`\`\`json
{
  "id": "data_987654321",
  "columns": [
    { "name": "sepal_length", "type": "numeric", "missing_count": 0 },
    { "name": "sepal_width", "type": "numeric", "missing_count": 0 },
    { "name": "petal_length", "type": "numeric", "missing_count": 0 },
    { "name": "petal_width", "type": "numeric", "missing_count": 0 },
    { "name": "species", "type": "categorical", "unique_values": 3 }
  ],
  "preview": [
    { "sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "species": "setosa" }
  ]
}
\`\`\`

---

### 4. Delete Dataset (\`DELETE /delete-dataset/{dataset_id}\`)
- **URL**: \`/delete-dataset/{dataset_id}\`
- **Method**: \`DELETE\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "message": "Dataset data_987654321 deleted successfully"
}
\`\`\`
`;

export const API_TRAINING_INFERENCE_MD_EN = `# API Reference: Training & Inference API

Primary API endpoints for launching AutoML optimization jobs, polling leaderboard metrics, and executing real-time inferences against deployed models.

---

## 🌐 Base URL
\`\`\`
http://localhost:8000
\`\`\`

---

## 📌 Endpoints

### 1. Launch AutoML Job (\`POST /train-from-requestbody-json/\`)
Dispatches a new automated machine learning training job into Apache Kafka.

- **URL**: \`/train-from-requestbody-json/?userId={userId}&id_data={id_data}\`
- **Method**: \`POST\`
- **Request Body (JSON)**:
\`\`\`json
{
  "task_type": "classification",
  "target_column": "species",
  "feature_columns": [
    "sepal_length",
    "sepal_width",
    "petal_length",
    "petal_width"
  ],
  "algorithms": [
    "RandomForest",
    "LightGBM",
    "LogisticRegression"
  ],
  "tuning_method": "bayesian",
  "metric": "f1_score",
  "cv_folds": 5
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "queued",
  "job_id": "job_20260416_001",
  "message": "Training task queued successfully via Kafka"
}
\`\`\`

---

### 2. Poll Job Status & Leaderboard (\`POST /get-job-info\`)
- **URL**: \`/get-job-info\`
- **Method**: \`POST\`
- **Request Body**: \`{"id": "job_20260416_001"}\`
- **Response (200 OK)**:
\`\`\`json
{
  "job_id": "job_20260416_001",
  "status": "completed",
  "progress": 100,
  "best_model": {
    "algorithm": "RandomForest",
    "score": 0.98,
    "metric": "f1_score",
    "hyperparameters": {
      "n_estimators": 100,
      "max_depth": 5,
      "criterion": "gini"
    }
  },
  "leaderboard": [
    { "rank": 1, "algorithm": "RandomForest", "accuracy": 0.98, "f1_score": 0.98 },
    { "rank": 2, "algorithm": "LightGBM", "accuracy": 0.96, "f1_score": 0.95 },
    { "rank": 3, "algorithm": "LogisticRegression", "accuracy": 0.92, "f1_score": 0.91 }
  ]
}
\`\`\`

---

### 3. Activate Model for Inference (\`POST /activate-model\`)
- **URL**: \`/activate-model?job_id={job_id}&activate=1\`
- **Method**: \`POST\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "message": "Model for job_20260416_001 is now active for inference"
}
\`\`\`

---

### 4. Execute Prediction / Inference (\`POST /inference-model/\`)
Submits new input records for real-time model inference.

- **URL**: \`/inference-model/?job_id={job_id}\`
- **Method**: \`POST\`
- **Content-Type**: \`multipart/form-data\`
- **Form Field**: \`file_data\` (CSV or JSON file containing rows to predict).
- **Response (200 OK)**:
\`\`\`json
{
  "job_id": "job_20260416_001",
  "predictions": [
    { "row_index": 0, "predicted_label": "setosa", "confidence": 0.992 },
    { "row_index": 1, "predicted_label": "versicolor", "confidence": 0.945 }
  ],
  "total_records": 2
}
\`\`\`

---

### 5. Python Integration Example
\`\`\`python
import requests

url = "http://localhost:8000/inference-model/?job_id=job_20260416_001"
files = {"file_data": open("test_data.csv", "rb")}
response = requests.post(url, files=files)

print("Predictions:", response.json())
\`\`\`
`;
