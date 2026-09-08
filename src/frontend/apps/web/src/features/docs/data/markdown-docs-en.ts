/**
 * Full English Markdown documentation mirrored from HAutoML docs
 * https://optivisionlab.github.io/AutoML/docs/
 */

export const INDEX_MD_EN = `# Welcome to HAutoML

**HAutoML** is an open-source **Automated Machine Learning (AutoML)** platform developed by [OptiVisionLab](https://optivisionlab.fit-haui.edu.vn/), School of Information and Communications Technology, Hanoi University of Industry (HaUI).

The platform automates the entire end-to-end machine learning lifecycle — from data preprocessing, model selection, hyperparameter tuning, to model deployment — enabling users to upload datasets and automatically generate high-quality machine learning models **without requiring in-depth expertise in programming or data science**.

## 🎯 Vision

HAutoML is designed to **democratize machine learning** — empowering anyone (students, business analysts, domain experts) to build effective machine learning models without needing to master complex low-level engineering and algorithmic nuances.

## ✨ Key Features

- **User Management & Authentication**: Secure registration/login system with OAuth 2.0 (Google) support.
- **Dataset Management**: Intuitive interface to upload, preview, update, and manage datasets.
- **Automated AutoML Pipeline**: 
  - 🔄 **Intelligent Data Preprocessing**: Automatic feature type detection (numeric, categorical, text) and application of appropriate transformers.
  - 🔍 **Hyperparameter Optimization**: Automated search for optimal parameter configurations (Grid Search, Random Search, Bayesian Optimization, Genetic Algorithms).
  - 🎯 **Model Selection**: Cross-model performance comparison to select the champion model.
- **Asynchronous Distributed Processing**: Powered by Apache Kafka to process training tasks concurrently and scalably.
- **Real-time Job Monitoring**: Live tracking of training pipeline stages and progress.
- **1-Click Deployment & Inference**: Simple REST API to serve instant predictions on new data.
- **Modern Web Interface**: Built with Next.js 15 + React 18 + TypeScript + Tailwind CSS.

## 🔬 Scientific Approach

HAutoML leverages state-of-the-art scientific methods in AutoML:

### Intelligent Data Preprocessing
- Automatic feature type detection (numeric, categorical, text)
- Tailored missing value imputation (median for numeric, mode for categorical)
- Robust normalization (\`StandardScaler\`) and one-hot encoding (\`OneHotEncoder\`)
- Anti-data-leakage pipeline design via \`scikit-learn ColumnTransformer\`

### Hyperparameter Search
- Grid Search and Random Search
- Bayesian Optimization (Gaussian Process) & Genetic Algorithms
- $k$-fold cross-validation ($k = 5$) to mitigate overfitting

### Model Evaluation
- **Classification**: Accuracy, Precision, Recall, F1-Score, Balanced Accuracy
- **Regression**: MAE, MSE, RMSE, $R^2$ Score
- Generalization validation to guard against overfitting

Read more in [Scientific Approach](/docs?topic=scientific-approach).

## 🏗️ System Architecture

HAutoML adopts a modern **microservices** architecture:

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                    Web User Interface                        │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│                  Backend (FastAPI)                          │
│              API, Business Logic, Orchestration              │
└─┬────────────┬──────────────┬─────────────┬─────────────────┘
  │            │              │             │
  │            │              │             │
┌─▼─┐    ┌────▼────┐    ┌────▼─────┐  ┌──▼───────┐
│   │    │ MongoDB │    │  Apache  │  │  MinIO   │
│   │    │(Database│    │  Kafka   │  │ (Storage │
│   │    │ Metadata│    │ (Queue)  │  │ Datasets)│
│   │    └─────────┘    └─────┬────┘  └──────────┘
│   │                         │
│   └─────────────────────────┼─────────────────────┐
│                             │ Task dispatch       │
└─────────────────────────────┼─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │       Workers       │
                   │  (Process Training  │
                   │   Jobs from Kafka)  │
                   └─────────────────────┘
\`\`\`

Read more in [System Architecture](/docs?topic=architecture).

## 🚀 Quickstart

### Simplest Method: Using Docker & Docker Compose

The recommended and fastest way to launch the full system is using Docker and Docker Compose.

**Prerequisites**: [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/install/)

\`\`\`bash
# Clone the repository
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML

# Configure environment variables from templates
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env

# Build and start all services
docker-compose up -d --build

# To stop the system
docker-compose down
\`\`\`

---

### Local Source Development

**1. Clone the project repository**
\`\`\`bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
\`\`\`

**2. Configure environment files**
\`\`\`bash
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env
\`\`\`

**3. Launch system components**

**Backend & Worker cluster** (in \`AutoML/src/backend\`):
\`\`\`bash
# Install Python dependencies
pip install -r requirements.txt

# Start API server (port 8000)
python app.py

# In a separate terminal, launch the Worker node
python -m cluster.worker
\`\`\`

**Frontend** (in \`AutoML/src/frontend\`):
\`\`\`bash
# Install dependencies
npm install

# Start Next.js development server (port 3000)
npm run dev
\`\`\`

**4. Access URLs**
- **Web User Interface**: [http://localhost:3000](http://localhost:3000)
- **Backend API Server**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚙️ Environment Variables

The system relies on environment variables to switch between local development and containerized Docker environments:

### Infrastructure
- \`MINIO_ENDPOINT\`: MinIO server host (default: \`localhost:9000\`; in Docker: \`minio:9000\`).
- \`KAFKA_SERVER\`: Kafka broker address (\`localhost:9092\`; in Docker: \`kafka:9092\`).
- \`MONGODB_CONNECT\`: MongoDB connection string (\`mongodb://localhost:27017\` or \`mongodb://mongodb:27017\`).

### Distributed Orchestration (Master - Worker)
- \`HOST_BACK_END\`: API listener host (set to \`0.0.0.0\` to accept external worker connections).
- \`WORKER_LIST\`: List of registered worker nodes.
- \`TASK_TIMEOUT_SECONDS\`: Maximum execution time before marking worker unresponsive.
- \`MAX_TASK_SNOOZES\`: Maximum automatic task retries on failure.

### Security & Authentication
- \`SECRET_KEY\`: Secret key used for JWT signing and verification.
- \`GOOGLE_CLIENT_ID\` / \`GOOGLE_CLIENT_SECRET\`: Google OAuth 2.0 credentials.
- \`ACCESS_EXPIRE\`: JWT Access Token expiry time in minutes.

---

## 📁 Project Structure

\`\`\`
AutoML/
├── docker-compose.yaml     # Multi-container orchestration
├── docs/                   # MkDocs documentation source
├── mkdocs.yml              # MkDocs configuration
├── src/
│   ├── backend/            # FastAPI, Kafka, Worker, AutoML Engine
│   │   ├── app.py          # FastAPI application entrypoint
│   │   ├── automl/         # Core AutoML engine & search algorithms
│   │   ├── cluster/        # Distributed Worker node processes
│   │   ├── data/           # Dataset handlers & MinIO upload
│   │   ├── database/       # MongoDB async drivers
│   │   └── users/          # Authentication & OAuth
│   └── frontend/           # Next.js 15 Monorepo (Web & Mobile shared)
│       ├── apps/web/       # Next.js web application
│       ├── packages/api/   # Universal API Client library
│       └── packages/domain/# Shared domain types & schemas
└── README.md
\`\`\`

## 👥 Contributors

We express sincere gratitude to everyone contributing to the HAutoML project at OptiVisionLab:

[![Contributors](https://contrib.rocks/image?repo=optivisionlab/AutoML)](https://github.com/optivisionlab/AutoML/graphs/contributors)

## 📄 Citation & License

If you use HAutoML in your academic research, please cite our Springer Nature publication:

\`\`\`bibtex
@InProceedings{Do2026HAutoML,
  author="Do, Manh Quang and Chu, Thi Anh and Ngo, Cong Binh and Bui, Huy Nam and Nguyen, Thi My Khanh and Nguyen, Thi Minh and Vu, Viet Thang",
  title="HAutoML: Open-Source for Automated Machine Learning",
  booktitle="Proceedings of the Fifth International Conference on Intelligent Systems and Networks",
  year="2026",
  publisher="Springer Nature Singapore",
  pages="415--423",
  isbn="978-981-95-1746-6"
}
\`\`\`

Distributed under the [Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/).
`;

export const GETTING_STARTED_MD_EN = `# Getting Started with HAutoML

This comprehensive guide covers installing, configuring, and running HAutoML via Docker Compose or directly from source code.

## 1. Quickstart: Using Docker & Docker Compose (Recommended)

The simplest and most reliable method to run the entire HAutoML stack is using **Docker** and **Docker Compose**.

**Prerequisites:**
- [Docker](https://www.docker.com/get-started) (version 20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0+)

> 💡 **Configuration Tip:**
> To avoid modifying \`docker-compose.yaml\`, simply copy and rename the template files from \`temp.env\` to \`.env\` in both the backend and frontend directories.

\`\`\`bash
# 1. Clone repository
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML

# 2. Setup environment variables
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env

# 3. Build and run all services in background
docker-compose up -d --build

# To stop all services
docker-compose down
\`\`\`

---

## 2. Local Source Development

If you wish to develop or modify the codebase directly, follow these steps:

### Step 1: Clone Repository
\`\`\`bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
\`\`\`

### Step 2: Configure Environment Files
\`\`\`bash
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env
\`\`\`

### Step 3: Launch System Services

**Backend & Worker Cluster (in \`AutoML/src/backend\`):**
\`\`\`bash
cd src/backend

# Install required Python packages
pip install -r requirements.txt

# Start FastAPI server on port 8000
python app.py

# In another terminal window, start the background Worker node
python -m cluster.worker
\`\`\`

**Frontend Web UI (in \`AutoML/src/frontend\`):**
\`\`\`bash
cd src/frontend

# Install node dependencies
npm install

# Start Next.js development server on port 3000
npm run dev
\`\`\`

### Step 4: Access Endpoints
- **Web UI**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 3. Environment Variables Reference

| Variable | Description | Default Local | Docker Value |
|---|---|---|---|
| \`MINIO_ENDPOINT\` | MinIO Storage endpoint | \`localhost:9000\` | \`minio:9000\` |
| \`MINIO_ACCESS_KEY\` | MinIO access username | \`minioadmin\` | \`minioadmin\` |
| \`MINIO_SECRET_KEY\` | MinIO access password | \`minioadmin\` | \`minioadmin\` |
| \`KAFKA_SERVER\` | Apache Kafka broker address | \`localhost:9092\` | \`kafka:9092\` |
| \`MONGODB_CONNECT\` | MongoDB connection URI | \`mongodb://localhost:27017\` | \`mongodb://mongodb:27017\` |
| \`SECRET_KEY\` | JWT token encryption key | Custom string | Custom string |
| \`ACCESS_EXPIRE\` | JWT token expiry (minutes) | \`60\` | \`60\` |
| \`HOST_BACK_END\` | Backend bind address | \`0.0.0.0\` | \`0.0.0.0\` |

> ⚠️ **Important Localhost Rule in Docker:**
> When running inside Docker containers, never use \`localhost\` for inter-service communication. Always use the service name defined in \`docker-compose.yaml\` (such as \`mongodb\`, \`kafka\`, \`minio\`).

---

## 4. Running MkDocs Documentation Locally

You can launch the static documentation server locally using MkDocs Material:

\`\`\`bash
# 1. Install MkDocs Material theme
pip install mkdocs-material

# 2. Run local development documentation server
mkdocs serve

# 3. Open browser and visit: http://127.0.0.1:8000
\`\`\`

---

## 5. Training Your First Model

Follow these 4 simple steps to train an ML model with HAutoML:

### Step 1: Upload Dataset
Navigate to **My Datasets**, click **Upload Dataset**, and select your \`.csv\` file (e.g. cardiovascular disease, customer churn, or housing prices). The dataset is uploaded securely into MinIO Storage.

### Step 2: Configure AutoML Task
In the Training Wizard:
1. **Target Column**: Select the column you wish to predict.
2. **Task Type**: Automatically detected as *Classification* or *Regression*.
3. **Features**: Choose feature columns or let the system auto-select.
4. **Metric**: Choose optimization metric (F1-Score, Accuracy, Balanced Accuracy, RMSE, MAE, $R^2$).

### Step 3: Run Training & Monitor Live
Click **Start Training**. The task is enqueued to Apache Kafka and dispatched to worker nodes:
\`\`\`
[Pipeline] Preprocessing dataset (imputation, scaling, one-hot encoding) → Done (0.6s)
[Worker 1] Tuning RandomForest with 5-Fold CV → Accuracy: 94.7% (3.2s)
[Worker 2] Tuning SupportVectorClassifier with RBF kernel → Accuracy: 91.5% (2.8s)
[Worker 3] Tuning GradientBoostingClassifier → Accuracy: 93.1% (4.1s)
[Master] Selected Best Model: RandomForestClassifier (Score: 0.947)
\`\`\`

### Step 4: 1-Click Deployment & Inference
Activate the model with 1 click, and run inference using standard cURL:
\`\`\`bash
curl -X POST "http://localhost:8000/inference-model/?job_id=job_9841" \\
  -F "file_data=@test_data.csv"
\`\`\`
`;

export const ARCHITECTURE_MD_EN = `# System Architecture

HAutoML is designed as a modern distributed microservices system, ensuring scalability, high availability, and optimal compute efficiency.

## Key System Components

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                    Web User Interface                        │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│                  Backend (FastAPI)                          │
│              API, Business Logic, Orchestration              │
└─┬────────────┬──────────────┬─────────────┬─────────────────┘
  │            │              │             │
  │            │              │             │
┌─▼─┐    ┌────▼────┐    ┌────▼─────┐  ┌──▼───────┐
│   │    │ MongoDB │    │  Apache  │  │  MinIO   │
│   │    │(Database│    │  Kafka   │  │ (Storage │
│   │    │ Metadata│    │ (Queue)  │  │ Datasets)│
│   │    └─────────┘    └─────┬────┘  └──────────┘
│   │                         │
│   └─────────────────────────┼─────────────────────┐
│                             │ Task dispatch       │
└─────────────────────────────┼─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │       Workers       │
                   │  (Process Training  │
                   │   Jobs from Kafka)  │
                   └─────────────────────┘
\`\`\`

### 1. Frontend (Next.js 15)
- **Framework**: Next.js 15 (React 18), TypeScript.
- **Styling & Components**: Tailwind CSS, Radix UI primitives, Lucide React icons.
- **State Management**: Redux Toolkit & React Context.
- **Internationalization**: \`next-intl\` with real-time language switching (Vietnamese & English).

### 2. Backend (FastAPI)
- **Framework**: Python 3.10+, FastAPI, Uvicorn.
- **Responsibilities**: REST API endpoints, user authentication (JWT & Google OAuth 2.0), training task scheduling, MinIO & Kafka integration.

### 3. Database (MongoDB)
- Stores user accounts, dataset metadata, AutoML job configurations, experiment logs, and model performance metrics.
- Connected via \`motor\` and \`pymongo\` asynchronous drivers.

### 4. Message Queue (Apache Kafka)
- Decouples API server and compute-heavy training workloads.
- Manages priority queues and distributes training partitions across workers.

### 5. Worker Cluster
- Independent Python consumer processes listening to Kafka topics.
- Executes data preprocessing, model selection, hyperparameter tuning, and model checkpointing.

### 6. Object Storage (MinIO)
- S3-compatible storage storing raw and processed dataset files (\`.csv\`) as well as trained model artifacts (\`.pkl\`, \`.joblib\`).

---

## Communication Protocols & Data Flow

1. **User Action**: The client uploads a dataset through Next.js.
2. **Data Storage**: FastAPI receives the file and streams it directly to MinIO Storage, saving metadata in MongoDB.
3. **Training Trigger**: The user configures AutoML parameters and clicks "Start Training".
4. **Task Enqueue**: FastAPI publishes the job configuration to Kafka topic \`automl_training_tasks\`.
5. **Parallel Execution**: Available Worker nodes consume the job, download data from MinIO, preprocess features, and evaluate model candidates in parallel.
6. **Result Aggregation**: Workers save candidate scores and champion model weights back to MinIO & MongoDB.
7. **Serving & Inference**: Client invokes REST inference endpoint, loading champion model into memory to return instant predictions.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 15, React 18, TypeScript, Tailwind CSS, Redux Toolkit, Axios, next-intl |
| **Backend** | Python, FastAPI, Uvicorn, Pydantic, Authlib, PyJWT |
| **Machine Learning** | Scikit-learn, Pandas, NumPy, Scikit-optimize, XGBoost |
| **Message Queue** | Apache Kafka, aiokafka, kafka-python |
| **Storage & Database** | MongoDB (pymongo), MinIO Object Storage |
| **DevOps & Containers** | Docker, Docker Compose |
`;

export const SCIENTIFIC_APPROACH_MD_EN = `# Scientific Approach & Methodology

HAutoML is an Automated Machine Learning (AutoML) platform that fully automates the end-to-end machine learning pipeline. This document outlines the scientific methodology, algorithms, and technical strategies applied across the system.

## 1. End-to-End AutoML Pipeline

\`\`\`
Raw Data ➔ Data Preprocessing ➔ Model Selection & HPO ➔ Champion Model ➔ 1-Click Inference
\`\`\`

### Phase 1: Intelligent Data Preprocessing

#### a) Feature Type Detection
- **Numeric Features**: Detected via \`pd.api.types.is_numeric_dtype()\`.
- **Categorical Features**: Columns with discrete values below a cardinality threshold.
- **Text Features**: High-cardinality string columns containing descriptive text.

#### b) Missing Value Imputation
- **Numeric**: Imputed using **Median**, offering robust resilience against outliers:
  $$\\tilde{x} = \\text{median}(X)$$
- **Categorical**: Imputed using the **Most Frequent (Mode)** value.

#### c) Normalization & Encoding
- **Numeric**: Normalized using \`StandardScaler\` (zero mean, unit variance):
  $$z = \\frac{x - \\mu}{\\sigma}$$
- **Categorical**: Encoded via \`OneHotEncoder(handle_unknown='ignore', sparse_output=True)\`.
- **Text**: Vectorized via \`TfidfVectorizer\`.

#### d) Anti-Data-Leakage Pipeline
All preprocessing stages are encapsulated within \`scikit-learn Pipeline\` and \`ColumnTransformer\`, ensuring that transformations are fit strictly on training splits and only applied to test/validation splits:

\`\`\`python
numeric_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=True))
])

preprocessor = ColumnTransformer(transformers=[
    ('num', numeric_transformer, numeric_cols),
    ('cat', categorical_transformer, categorical_cols)
])
\`\`\`

---

### Phase 2: Model Selection & Hyperparameter Optimization (HPO)

#### a) Optimization Strategies
1. **Grid Search**: Exhaustive search over predefined discrete hyperparameter grids.
2. **Random Search**: Random sampling from continuous and discrete probability distributions.
3. **Bayesian Optimization (v2.1+)**: Employs Gaussian Process regression to model the objective function and choose evaluation points with Expected Improvement (EI).
4. **Genetic Algorithm (v2.1+)**: Evolves hyperparameter candidate populations through selection, crossover, and mutation operators.

#### b) Cross-Validation
Uses $k$-fold cross-validation (default $k = 5$) to obtain unbiased performance estimates:
$$\\text{CV Score} = \\frac{1}{k} \\sum_{i=1}^{k} \\text{Score}_i$$

#### c) Evaluation Metrics

**For Classification:**
- **Accuracy**: Overall proportion of correct predictions.
- **Precision**: Positive predictive value.
- **Recall (Sensitivity)**: True positive rate.
- **F1-Score**: Harmonic mean of Precision and Recall:
  $$\\text{F1} = 2 \\times \\frac{\\text{Precision} \\times \\text{Recall}}{\\text{Precision} + \\text{Recall}}$$
- **Balanced Accuracy**: Macro-averaged recall across classes, essential for imbalanced datasets.

**For Regression:**
- **MAE (Mean Absolute Error)**: Average absolute magnitude of errors:
  $$\\text{MAE} = \\frac{1}{n} \\sum_{i=1}^{n} |y_i - \\hat{y}_i|$$
- **MSE (Mean Squared Error)**: Average squared differences.
- **RMSE (Root Mean Squared Error)**: Standard deviation of residuals:
  $$\\text{RMSE} = \\sqrt{\\frac{1}{n} \\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2}$$
- **$R^2$ Score (Coefficient of Determination)**: Proportion of variance explained by model:
  $$R^2 = 1 - \\frac{\\sum (y_i - \\hat{y}_i)^2}{\\sum (y_i - \\bar{y})^2}$$

---

## 2. Asynchronous Queue Processing with Kafka

\`\`\`
Frontend ➔ FastAPI Backend ➔ Kafka Queue ➔ Distributed Workers ➔ MongoDB Results
\`\`\`

**Key Architectural Benefits:**
- **Horizontal Scalability**: Add more worker nodes dynamically to process training jobs in parallel.
- **Fault Tolerance**: If a worker fails mid-training, tasks are re-queued and reassigned automatically.
- **Decoupled User Experience**: Frontend stays fast and responsive without blocking on long training operations.
`;

export const BACKEND_API_MD_EN = `# Backend API Documentation (FastAPI)

Complete technical reference for all REST API endpoints available on the HAutoML backend server at \`http://localhost:8000\`.

Interactive Swagger UI is accessible at: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 1. Authentication & User Management (Auth)

### \`POST /auth/register\`
Register a new user account with email and password.
- **Request Body**:
\`\`\`json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Nguyen Van A"
}
\`\`\`
- **Response**: \`201 Created\` with user object.

### \`POST /auth/login\`
Authenticate user credentials and issue JWT access token.
- **Request Body**: \`username\` (email) and \`password\` (Form Data / OAuth2PasswordRequestForm).
- **Response**:
\`\`\`json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
\`\`\`

### \`GET /auth/me\`
Retrieve profile details for currently authenticated user.
- **Headers**: \`Authorization: Bearer <access_token>\`

---

## 2. Dataset Management (Datasets)

### \`GET /data/list\`
List all uploaded datasets belonging to the current user.

### \`POST /data/upload\`
Upload a new dataset file (\`.csv\`) to MinIO Storage.
- **Content-Type**: \`multipart/form-data\`
- **Parameters**: \`file\` (file binary), \`name\` (string), \`description\` (string).

### \`GET /data/{dataset_id}\`
Retrieve detailed schema and statistical overview of a dataset.

### \`DELETE /data/{dataset_id}\`
Remove dataset and its stored files from MinIO and MongoDB.

---

## 3. AutoML Training & Inference

### \`POST /v2/auto/jobs/training\`
Create and enqueue an asynchronous AutoML training job.
- **Request Body**:
\`\`\`json
{
  "id_data": "dataset_6789",
  "id_user": "user_1234",
  "config": {
    "problem_type": "classification",
    "target": "target_column",
    "list_feature": ["feature_1", "feature_2", "feature_3"],
    "search_algorithm": "bayesian_search",
    "metric_sort": "f1_score"
  }
}
\`\`\`

### \`GET /v2/auto/jobs/{job_id}\`
Poll current status and real-time logs of a training job.
- **Status values**: \`submitted\`, \`queued\`, \`processing\`, \`completed\`, \`failed\`.

### \`POST /inference-model/\`
Perform batch predictions on new CSV data using a trained champion model.
- **Parameters**: \`job_id\` (query parameter), \`file_data\` (multipart CSV file).
- **Response**: CSV stream or JSON array containing predicted target labels/values.
`;

export const RELEASES_MD_EN = `# Release History & Changelog

This page chronicles all official releases of the HAutoML platform along with major features and enhancements.

---

## v2.2.0 (15/01/2026) - Current Stable
*Distributed Worker Scaling & Full Next.js 15 Monorepo*

- **Distributed Orchestration**: Automatic worker node discovery, task timeout monitoring, and automated failover.
- **Universal API Layer**: Shared \`@automl/api\` and \`@automl/domain\` packages supporting both Web and Mobile.
- **UI & UX Revamp**: Interactive documentation, ⌘K search modal, real-time training progress map.
- **Contributors**: @VanAnh-13, @xuanndong, @vanhdz74, @DoManhQuang.

---

## v2.1.0 (05/12/2025)
*Optima Search: Bayesian Optimization & Genetic Algorithms*

- **Advanced Hyperparameter Optimization**: Integrated Gaussian Process Bayesian Optimization and Genetic Algorithms.
- **Worker Management**: Enhanced cluster worker lifecycle and task queue assignment.
- **Basic Text Preprocessing**: String tokenization and TF-IDF feature extraction.
- **Containerization**: Updated Dockerfile and multi-stage Docker Compose recipes.

---

## v2.0.0 (10/10/2025)
*Microservices Architecture & Apache Kafka*

- **Microservices Shift**: Decoupled monolithic backend into FastAPI, Apache Kafka queue, and distributed Python workers.
- **Object Storage**: Migrated dataset and model storage to MinIO S3-compatible object storage.
- **Model Marketplace**: Community catalog for sharing and loading pre-trained pipelines.

---

## v1.0.0 (15/06/2025)
*Initial Open Source Release*

- Core AutoML engine supporting basic classification and regression with Scikit-learn.
- Grid Search and Random Search algorithms.
- Single-page dashboard for dataset upload and model evaluation.
`;

export const CITATION_LICENSE_MD_EN = `# Citation & License

Academic citation information and license agreements for the HAutoML project.

## Academic Publication (Recommended) 📄

If you utilize HAutoML in your research, scientific benchmarks, or publications, please cite the following paper:

\`\`\`bibtex
@InProceedings{Do2026HAutoML,
  author="Do, Manh Quang
  and Chu, Thi Anh
  and Ngo, Cong Binh
  and Bui, Huy Nam
  and Nguyen, Thi My Khanh
  and Nguyen, Thi Minh
  and Vu, Viet Thang",
  editor="Thi Dieu Linh, Nguyen
  and Yu, Shiqi
  and Selamat, Ali
  and Tran, Duc-Tan",
  title="HAutoML: Open-Source for Automated Machine Learning",
  booktitle="Proceedings of the Fifth International Conference on Intelligent Systems and Networks",
  year="2026",
  publisher="Springer Nature Singapore",
  address="Singapore",
  pages="415--423",
  isbn="978-981-95-1746-6"
}
\`\`\`

**Full Reference:**
Do, M. Q., Chu, T. A., Ngo, C. B., Bui, H. N., Nguyen, T. M. K., Nguyen, T. M., & Vu, V. T. (2026). HAutoML: Open-Source for Automated Machine Learning. In *Proceedings of the Fifth International Conference on Intelligent Systems and Networks* (pp. 415–423). Springer Nature Singapore. [https://doi.org/10.1007/978-981-95-1746-6_46](https://doi.org/10.1007/978-981-95-1746-6_46)

---

## Software Citation 💻

You can also cite the software repository directly:

\`\`\`bibtex
@software{hautoml2024,
  title = {HAutoML: Open-source Automated Machine Learning Platform},
  author = {OptiVisionLab},
  url = {https://github.com/optivisionlab/AutoML},
  year = {2024},
  license = {CC BY-NC 4.0}
}
\`\`\`

---

## License

This project is licensed under the [Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)](https://creativecommons.org/licenses/by-nc/4.0/).

Please see the [LICENSE](https://github.com/optivisionlab/AutoML/blob/main/LICENSE) file for complete terms. This software is released strictly for **academic and research purposes**. Commercial use is **prohibited** without prior written permission from OptiVisionLab.
`;

import {
  FIRST_TRAINING_MD_EN,
  DISTRIBUTED_COMPUTING_MD_EN,
  HPO_TUNING_MD_EN,
  EVALUATION_METRICS_MD_EN,
  API_AUTH_MD_EN,
  API_DATASETS_MD_EN,
  API_TRAINING_INFERENCE_MD_EN,
} from "./markdown-docs-topics-en";

export const DOCS_PAGES_EN: Record<string, { title: string; markdown: string }> = {
  overview: {
    title: "Home (Overview)",
    markdown: INDEX_MD_EN,
  },
  "getting-started": {
    title: "Quickstart Guide",
    markdown: GETTING_STARTED_MD_EN,
  },
  "first-training": {
    title: "First Model Training",
    markdown: FIRST_TRAINING_MD_EN,
  },
  architecture: {
    title: "System Microservices Architecture",
    markdown: ARCHITECTURE_MD_EN,
  },
  "distributed-computing": {
    title: "Distributed Computing & Workers",
    markdown: DISTRIBUTED_COMPUTING_MD_EN,
  },
  "scientific-approach": {
    title: "AutoML Pipeline & Preprocessing",
    markdown: SCIENTIFIC_APPROACH_MD_EN,
  },
  "hpo-tuning": {
    title: "Hyperparameter Search (HPO)",
    markdown: HPO_TUNING_MD_EN,
  },
  "evaluation-metrics": {
    title: "Model Evaluation Metrics",
    markdown: EVALUATION_METRICS_MD_EN,
  },
  "backend-api": {
    title: "Backend API (FastAPI)",
    markdown: BACKEND_API_MD_EN,
  },
  "api-auth": {
    title: "User Management & Auth API",
    markdown: API_AUTH_MD_EN,
  },
  "api-datasets": {
    title: "Dataset Management API",
    markdown: API_DATASETS_MD_EN,
  },
  "api-training-inference": {
    title: "Training & Inference API",
    markdown: API_TRAINING_INFERENCE_MD_EN,
  },
  releases: {
    title: "Release History & Changelog",
    markdown: RELEASES_MD_EN,
  },
  "citation-license": {
    title: "Citation & License",
    markdown: CITATION_LICENSE_MD_EN,
  },
};
