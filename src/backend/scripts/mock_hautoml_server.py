"""
Mock HAutoML Server — Giả lập training backend cho CI/CD.

Simulate đầy đủ API endpoints:
- /home → health check
- /get-list-data-by-userid → list datasets
- /get-data-info → dataset info
- /api/v1/available-models/{type} → available models
- /train-from-requestbody-json/ → start training
- /get-job-info → job status + results
- /get-list-job-by-userId → list jobs
"""

from __future__ import annotations

import json
import time
import uuid
import argparse
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


# ── Mock Data ────────────────────────────────────────────

STUDENT_DATASET = {
    "id": "ds_student_001",
    "name": "Student Performance",
    "filename": "student_performance.csv",
    "n_rows": 395,
    "n_cols": 33,
    "features": [
        "school", "sex", "age", "address", "famsize", "Pstatus",
        "Medu", "Fedu", "Mjob", "Fjob", "reason", "guardian",
        "traveltime", "studytime", "failures", "schoolsup",
        "famsup", "paid", "activities", "nursery", "higher",
        "internet", "romantic", "famrel", "freetime", "goout",
        "Dalc", "Walc", "health", "absences", "G1", "G2",
    ],
    "target": "G3",
    "problem_type": "regression",
    "created_at": "2024-01-15T10:00:00Z",
    "user_id": "ci_user",
}

AVAILABLE_MODELS = {
    "regression": {
        "models": [
            {
                "name": "RandomForestRegressor",
                "display_name": "Random Forest",
                "category": "ensemble",
                "hyperparameters": {
                    "n_estimators": {"type": "int", "default": 100, "range": [10, 500]},
                    "max_depth": {"type": "int", "default": None, "range": [1, 50]},
                },
            },
            {
                "name": "XGBRegressor",
                "display_name": "XGBoost",
                "category": "gradient_boosting",
                "hyperparameters": {
                    "n_estimators": {"type": "int", "default": 100, "range": [10, 500]},
                    "learning_rate": {"type": "float", "default": 0.1, "range": [0.01, 1.0]},
                },
            },
            {
                "name": "SVR",
                "display_name": "Support Vector Regression",
                "category": "svm",
                "hyperparameters": {
                    "C": {"type": "float", "default": 1.0, "range": [0.01, 100]},
                    "kernel": {"type": "str", "default": "rbf", "options": ["linear", "rbf", "poly"]},
                },
            },
            {
                "name": "LinearRegression",
                "display_name": "Linear Regression",
                "category": "linear",
                "hyperparameters": {},
            },
        ],
        "default_metric": "rmse",
        "available_metrics": ["rmse", "mae", "r2", "mse"],
    },
    "classification": {
        "models": [
            {
                "name": "RandomForestClassifier",
                "display_name": "Random Forest",
                "category": "ensemble",
            },
            {
                "name": "XGBClassifier",
                "display_name": "XGBoost",
                "category": "gradient_boosting",
            },
            {
                "name": "SVC",
                "display_name": "Support Vector Machine",
                "category": "svm",
            },
        ],
        "default_metric": "accuracy",
        "available_metrics": ["accuracy", "f1", "precision", "recall"],
    },
}

# Training results (simulated)
TRAINING_RESULTS = {
    "RandomForestRegressor": {"rmse": 1.82, "mae": 1.34, "r2": 0.87, "mse": 3.31},
    "XGBRegressor": {"rmse": 1.65, "mae": 1.21, "r2": 0.91, "mse": 2.72},
    "SVR": {"rmse": 2.15, "mae": 1.58, "r2": 0.82, "mse": 4.62},
    "LinearRegression": {"rmse": 2.45, "mae": 1.89, "r2": 0.76, "mse": 6.00},
}

# Active jobs storage
active_jobs: dict[str, dict] = {}


# ── Request Handler ──────────────────────────────────────


class MockHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _parse_params(self):
        parsed = urlparse(self.path)
        return parse_qs(parsed.query)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        path = urlparse(self.path).path
        params = self._parse_params()

        # Health check
        if path == "/home":
            self._send_json({"status": "ok", "service": "HAutoML-Mock", "version": "ci"})

        # Available models
        elif path.startswith("/api/v1/available-models/"):
            ptype = path.split("/")[-1]
            if ptype in AVAILABLE_MODELS:
                self._send_json(AVAILABLE_MODELS[ptype])
            else:
                self._send_json({"error": f"Unknown problem type: {ptype}"}, 400)

        # Dataset info
        elif path == "/get-data-info":
            ds_id = params.get("id", [""])[0]
            if ds_id == STUDENT_DATASET["id"]:
                self._send_json(STUDENT_DATASET)
            else:
                self._send_json({"error": f"Dataset not found: {ds_id}"}, 404)

        else:
            self._send_json({"error": f"Unknown endpoint: {path}"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        params = self._parse_params()
        body = self._read_body()

        # List datasets
        if path == "/get-list-data-by-userid":
            self._send_json({
                "datasets": [STUDENT_DATASET],
                "total": 1,
            })

        # Start training
        elif path == "/train-from-requestbody-json/":
            user_id = params.get("userId", ["ci_user"])[0]
            dataset_id = params.get("id_data", [""])[0]
            models = body.get("models", ["RandomForestRegressor", "XGBRegressor", "SVR"])
            target = body.get("target_column", "G3")
            problem_type = body.get("problem_type", "regression")

            job_id = f"job_{uuid.uuid4().hex[:8]}"

            # Simulate training results
            model_results = []
            best_model = None
            best_score = float("inf")
            for m in models:
                metrics = TRAINING_RESULTS.get(m, {"rmse": random.uniform(1.5, 3.0)})
                model_results.append({"model": m, "metrics": metrics})
                if metrics.get("rmse", 999) < best_score:
                    best_score = metrics["rmse"]
                    best_model = m

            job_data = {
                "id": job_id,
                "job_id": job_id,
                "user_id": user_id,
                "dataset_id": dataset_id,
                "problem_type": problem_type,
                "target_column": target,
                "models_requested": models,
                "status": "completed",
                "best_model": best_model,
                "best_score": round(best_score, 4),
                "model_results": model_results,
                "metrics": TRAINING_RESULTS.get(best_model, {}),
                "started_at": "2024-06-24T10:00:00Z",
                "finished_at": "2024-06-24T10:05:00Z",
                "training_time_seconds": 300,
            }
            active_jobs[job_id] = job_data

            self._send_json(job_data)
            print(f"  ✓ Training started: {job_id} | models={models} | best={best_model}")

        # Job info
        elif path == "/get-job-info":
            job_id = params.get("id", [""])[0]
            if job_id in active_jobs:
                self._send_json(active_jobs[job_id])
            else:
                self._send_json({"error": f"Job not found: {job_id}"}, 404)

        # List jobs
        elif path == "/get-list-job-by-userId":
            jobs = list(active_jobs.values())
            self._send_json({"jobs": jobs, "total": len(jobs)})

        else:
            self._send_json({"error": f"Unknown POST endpoint: {path}"}, 404)

    def log_message(self, format, *args):
        print(f"  [MockHAutoML] {args[0]}")


# ── Server ───────────────────────────────────────────────


def start_server(port: int = 8585, background: bool = False):
    server = HTTPServer(("0.0.0.0", port), MockHandler)
    print(f"✓ Mock HAutoML Server running on port {port}")
    print(f"  Endpoints: /home, /get-list-data-by-userid, /get-data-info,")
    print(f"  /api/v1/available-models/{{type}}, /train-from-requestbody-json/,")
    print(f"  /get-job-info, /get-list-job-by-userId")
    print(f"  Dataset: Student Performance (395 rows × 33 cols)")
    print()

    if background:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    else:
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock HAutoML Server")
    parser.add_argument("--port", type=int, default=8585)
    args = parser.parse_args()
    start_server(args.port)
