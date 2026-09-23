import json
from datetime import datetime, timezone
from typing import Any

from src.modules.inference.schemas import CodeSnippets


class CodeSnippetGenerator:
    @staticmethod
    def generate_all(endpoint_url: str, sample_payload: dict[str, Any]) -> CodeSnippets:
        json_payload_str = json.dumps(sample_payload, indent=2)
        escaped_json_str = json.dumps(json.dumps(sample_payload))

        curl_snippet = (
            f"curl -X POST \"{endpoint_url}\" \\\n"
            f"  -H \"Authorization: Bearer <YOUR_ACCESS_TOKEN>\" \\\n"
            f"  -H \"Content-Type: application/json\" \\\n"
            f"  -d '{json.dumps(sample_payload)}'"
        )

        python_snippet = (
            f"import requests\n\n"
            f"url = \"{endpoint_url}\"\n"
            f"headers = {{\n"
            f"    \"Authorization\": \"Bearer <YOUR_ACCESS_TOKEN>\",\n"
            f"    \"Content-Type\": \"application/json\"\n"
            f"}}\n"
            f"payload = {json_payload_str}\n\n"
            f"response = requests.post(url, json=payload, headers=headers)\n"
            f"print(response.json())\n"
        )

        js_snippet = (
            f"const url = \"{endpoint_url}\";\n"
            f"const payload = {json_payload_str};\n\n"
            f"fetch(url, {{\n"
            f"  method: \"POST\",\n"
            f"  headers: {{\n"
            f"    \"Authorization\": \"Bearer <YOUR_ACCESS_TOKEN>\",\n"
            f"    \"Content-Type\": \"application/json\"\n"
            f"  }},\n"
            f"  body: JSON.stringify(payload)\n"
            f"}})\n"
            f".then(res => res.json())\n"
            f".then(data => console.log(data))\n"
            f".catch(err => console.error(err));\n"
        )

        csharp_snippet = (
            f"using System.Net.Http;\n"
            f"using System.Text;\n"
            f"using System.Text.Json;\n\n"
            f"var client = new HttpClient();\n"
            f"client.DefaultRequestHeaders.Add(\"Authorization\", \"Bearer <YOUR_ACCESS_TOKEN>\");\n"
            f"var jsonContent = new StringContent(\n"
            f"    {escaped_json_str},\n"
            f"    Encoding.UTF8,\n"
            f"    \"application/json\"\n"
            f");\n"
            f"var response = await client.PostAsync(\"{endpoint_url}\", jsonContent);\n"
            f"var result = await response.Content.ReadAsStringAsync();\n"
            f"Console.WriteLine(result);\n"
        )

        php_snippet = (
            f"<?php\n"
            f"$ch = curl_init(\"{endpoint_url}\");\n"
            f"$payload = json_encode({json.dumps(sample_payload)});\n\n"
            f"curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);\n"
            f"curl_setopt($ch, CURLOPT_HTTPHEADER, [\n"
            f"    'Authorization: Bearer <YOUR_ACCESS_TOKEN>',\n"
            f"    'Content-Type: application/json'\n"
            f"]);\n"
            f"curl_setopt($ch, CURLOPT_POST, true);\n"
            f"curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);\n\n"
            f"$response = curl_exec($ch);\n"
            f"curl_close($ch);\n"
            f"echo $response;\n"
            f"?>\n"
        )

        return CodeSnippets(
            curl=curl_snippet,
            python=python_snippet,
            javascript=js_snippet,
            csharp=csharp_snippet,
            php=php_snippet,
        )


class DockerPackageTemplate:
    REQUIREMENTS_TXT: str = (
        "fastapi==0.115.0\n"
        "uvicorn[standard]==0.31.0\n"
        "pydantic==2.9.2\n"
        "scikit-learn==1.5.1\n"
        "pandas==2.2.2\n"
        "numpy==1.26.2\n"
    )

    DOCKERFILE: str = (
        "FROM python:3.12-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY . .\n"
        "EXPOSE 8000\n"
        "CMD [\"uvicorn\", \"app:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n"
    )

    @staticmethod
    def generate_app_py(model_name: str, features: list[str]) -> str:
        return (
            "import os\n"
            "import pickle\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "from typing import Any, List\n"
            "from pydantic import BaseModel, Field\n"
            "from fastapi import FastAPI, HTTPException\n\n"
            "app = FastAPI(title=\"HAutoML Standalone Inference Service\", version=\"1.0.0\")\n\n"
            "MODEL_PATH = os.getenv(\"MODEL_PATH\", \"model.pkl\")\n"
            f"FEATURE_COLS = {json.dumps(features)}\n\n"
            "with open(MODEL_PATH, \"rb\") as f:\n"
            "    loaded_obj = pickle.load(f)\n\n"
            "if isinstance(loaded_obj, dict) and \"model\" in loaded_obj:\n"
            "    model = loaded_obj[\"model\"]\n"
            "    preprocessor = loaded_obj.get(\"preprocessor\")\n"
            "else:\n"
            "    model = loaded_obj\n"
            "    preprocessor = None\n\n"
            "class PredictRequest(BaseModel):\n"
            "    data: List[dict[str, Any]] = Field(..., min_length=1)\n\n"
            "@app.get(\"/health\")\n"
            "def health_check():\n"
            f"    return {{\"status\": \"healthy\", \"model\": \"{model_name}\"}}\n\n"
            "@app.post(\"/predict\")\n"
            "def predict(req: PredictRequest):\n"
            "    try:\n"
            "        df = pd.DataFrame(req.data)\n"
            "        if preprocessor is not None:\n"
            "            X = preprocessor.transform(df)\n"
            "            raw_preds = model.predict(X)\n"
            "            preds = preprocessor.inverse_transform_target(raw_preds)\n"
            "        else:\n"
            "            if FEATURE_COLS:\n"
            "                df = df[FEATURE_COLS].fillna(0.0)\n"
            "            X = df.to_numpy(dtype=np.float64)\n"
            "            preds = model.predict(X).tolist()\n"
            "        return {\"predictions\": preds, \"total_samples\": len(preds)}\n"
            "    except Exception as e:\n"
            "        raise HTTPException(status_code=400, detail=str(e))\n"
        )

    @staticmethod
    def generate_readme_md(model_name: str, job_id: str, features: list[str]) -> str:
        sample_dict = {f: 1.0 for f in features} if features else {"feature_1": 1.0}
        return (
            f"# Standalone Deployment Package: {model_name}\n\n"
            f"Trained model exported from HAutoML.\n\n"
            f"## Quick Start with Docker\n\n"
            f"```bash\n"
            f"# 1. Build Docker image\n"
            f"docker build -t hautoml-model-{job_id[:8]} .\n\n"
            f"# 2. Run Container\n"
            f"docker run -d -p 8000:8000 --name my-model hautoml-model-{job_id[:8]}\n\n"
            f"# 3. Test Prediction\n"
            f"curl -X POST http://localhost:8000/predict \\\n"
            f"  -H \"Content-Type: application/json\" \\\n"
            f"  -d '{{\"data\": [{json.dumps(sample_dict)}]}}'\n"
            f"```\n"
        )


class NotebookTemplate:
    @staticmethod
    def generate_notebook_dict(
        model_name: str,
        best_params: dict[str, Any],
        best_score: float,
        features: list[str],
        target: str,
    ) -> dict[str, Any]:
        return {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# HAutoML Generated Model Training Pipeline\n",
                        f"**Target Model**: `{model_name}`  \n",
                        f"**Optimization Metric Score**: `{best_score}`  \n",
                        f"**Generated Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n",
                    ],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "import numpy as np\n",
                        "import pandas as pd\n",
                        "import pickle\n",
                        "from sklearn.model_selection import StratifiedKFold, cross_val_score\n",
                        "from sklearn.preprocessing import StandardScaler, LabelEncoder\n",
                        "from sklearn.metrics import classification_report, accuracy_score\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["## 1. Model Configuration & Hyperparameters"],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        f"FEATURE_COLS = {json.dumps(features, indent=2)}\n",
                        f"TARGET_COL = '{target}'\n",
                        f"BEST_HYPERPARAMS = {json.dumps(best_params, indent=2)}\n\n",
                        "import sklearn.ensemble, sklearn.tree, sklearn.linear_model, sklearn.svm, sklearn.neighbors\n",
                        f"model_cls = getattr(sklearn.ensemble, '{model_name}', None) or getattr(sklearn.tree, '{model_name}', None) or getattr(sklearn.linear_model, '{model_name}', None)\n",
                        "model = model_cls(**BEST_HYPERPARAMS)\n",
                        "print('Model initialized with params:', BEST_HYPERPARAMS)\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["## 2. Training and Evaluation Pipeline"],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "# Load your dataset here:\n",
                        "# df = pd.read_csv('your_dataset.csv')\n\n",
                        "# Sample synthetic verification:\n",
                        "X_dummy = np.random.randn(100, len(FEATURE_COLS))\n",
                        "y_dummy = np.random.randint(0, 2, size=100)\n\n",
                        "model.fit(X_dummy, y_dummy)\n",
                        "preds = model.predict(X_dummy)\n",
                        "print('Sample verification accuracy:', accuracy_score(y_dummy, preds))\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["## 3. Save Standalone Model Artifact"],
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "with open('best_model.pkl', 'wb') as f:\n",
                        "    pickle.dump(model, f)\n",
                        "print('Model successfully saved to best_model.pkl')\n",
                    ],
                },
            ],
            "metadata": {
                "language_info": {"name": "python", "version": "3.12"},
            },
            "nbformat": 4,
            "nbformat_minor": 4,
        }
