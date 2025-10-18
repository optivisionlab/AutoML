import asyncio
import base64
import os
from typing import Dict, Any, List
import yaml

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter

load_dotenv()

NUMBER_WORKERS = int(os.getenv('NUMBER_WORKERS', 1))
WORKER_HOST = os.getenv('WORKER_HOST', 'localhost')
WORKER_BASE_PORT = int(os.getenv('WORKER_BASE_PORT', 8000))
WORKERS = [f"http://{WORKER_HOST}:{WORKER_BASE_PORT + i}" for i in range(NUMBER_WORKERS)]


def get_models():
    base_dir = "assets/system_models"
    file_path = os.path.join(base_dir, "model.yml")
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    models = {}
    for key, model_info in data['Classification_models'].items():
        models[key] = {
            "model": model_info["model"],
            "params": model_info['params']
        }

    metric_list = data['metric_list']
    return models, metric_list 


class JobManager:
    """Quản lý toàn bộ vòng đời của một job training."""
    def __init__(self, job_id: str, id_data: str, id_user: str, config: Dict[str, Any], server_url: str):
        self.job_id = job_id
        self.id_data = id_data
        self.id_user = id_user
        self.config = config
        self.server_url = server_url # URL để worker gọi lại
        
        self.task_queue = asyncio.Queue()
        self.results: List[Dict[str, Any]] = []
        self.total_tasks = 0
        self.completed_tasks = 0
        self.completion_event = asyncio.Event()
        self.final_result = None

    async def setup_tasks(self):
        """Chuẩn bị hàng đợi task."""
        models, metric_list = await asyncio.to_thread(get_models)
        self.total_tasks = len(models)
        for model_id, model_info in models.items():
            task = {"job_id": self.job_id, "model_info": model_info, "metrics": metric_list}
            await self.task_queue.put(task)

    def get_task(self):
        try:
            task_data = self.task_queue.get_nowait()
            # Bổ sung thông tin chung vào task để gửi cho worker
            task_data["id_data"] = self.id_data
            task_data["config"] = self.config
            return task_data
        except asyncio.QueueEmpty:
            return None

    def submit_result(self, result: Dict[str, Any]):
        self.results.append(result)
        self.completed_tasks += 1
        print(f"[{self.job_id}] Progress: {self.completed_tasks}/{self.total_tasks}")
        if self.completed_tasks >= self.total_tasks:
            self.completion_event.set()

    def reduce(self):
        """Tổng hợp kết quả cuối cùng"""
        valid_results = [r for r in self.results if r.get("success")]
        if not valid_results:
            raise ValueError("No successful results from workers.")
                
        final_model_scores = []
        for i, result in enumerate(valid_results):
            score_entry = {
                "model_id": i,
                "model_name": result["model_name"],
                "scores": result.get("scores"),
                "best_params": result.get("best_params", {})
            }
            final_model_scores.append(score_entry)

        metric_to_sort_by = self.config.get("metric_sort", "accuracy")
        best_model_info_in_list = max(
            final_model_scores, 
            key=lambda x: x["scores"].get(metric_to_sort_by, -1.0)
        )

        # Tìm lại task có chỉ số cao nhất
        original_best_result = next(
            r for r in valid_results if r["model_name"] == best_model_info_in_list["model_name"]
        )
        
        model_bytes = base64.b64decode(original_best_result["model_base64"])
    
        self.final_result = {
            "best_model_id": str(best_model_info_in_list["model_id"]),
            "model": model_bytes,
            "best_model": best_model_info_in_list["model_name"],
            "best_score": original_best_result["score"],
            "best_params": best_model_info_in_list.get("best_params", {}),
            "model_scores": final_model_scores
        }

    async def run(self):
        """Hàm chính điều phối toàn bộ job."""
        print(f"[{self.job_id}] Starting job coordination...")
        await self.setup_tasks()
        
        # Phát tín hiệu cho worker
        async with httpx.AsyncClient() as client:
            payload = {"master_api_url": self.server_url, "job_id": self.job_id}
            tasks = [client.post(f"{url}/control/start-work", json=payload) for url in WORKERS]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Chờ job hoàn thành
        await self.completion_event.wait()
        
        # Thực hiện reduce
        self.reduce()
        print(f"[{self.job_id}] Job finished coordination.")
        return self.final_result


ACTIVE_JOBS: dict[str, JobManager] = {}

mas = APIRouter()

# --- API NỘI BỘ CHO WORKER ---
@mas.get("/jobs/{job_id}/task")
async def get_task_for_worker(job_id: str):
    manager = ACTIVE_JOBS.get(job_id)
    if not manager: return {"task": None}
    return {"task": manager.get_task()}


@mas.post("/jobs/{job_id}/result")
async def submit_result_from_worker(job_id: str, result: dict):
    manager = ACTIVE_JOBS.get(job_id)
    if manager:
        manager.submit_result(result)
        return {"status": "received"}
    return {"status": "job_not_found"}