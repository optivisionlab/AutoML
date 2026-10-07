"""API dữ liệu mẫu cho pipeline huấn luyện, chạy độc lập với backend.

Chạy (trong thư mục này):
    uvicorn mock_api:app --port 8001 --reload

Gọi:
    POST http://localhost:8001/get-pipeline-sample
    Header: Authorization: Bearer <token>
    Body:   {"problem_type": "regression"}
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


PROFILE_DIR = Path(__file__).parent / "profiles"

# problem_type -> file JSON mẫu
SAMPLE_FILES = {
    "regression": "regresion_v1.json",
}

app = FastAPI(title="Training Pipeline Mock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineSampleRequest(BaseModel):
    problem_type: str
    job_id: Optional[str] = None


# Trả lỗi body sai dạng {"detail": "<chuỗi>"} giống các lỗi khác
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    reasons = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'] if p != 'body')}: {err['msg']}" for err in exc.errors()
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"Dữ liệu gửi lên không hợp lệ: {reasons}"},
    )


@app.post("/get-pipeline-sample")
async def get_pipeline_sample(
    body: PipelineSampleRequest,
    authorization: Optional[str] = Header(default=None),
):
    # API mẫu chỉ kiểm tra có Bearer token, không xác thực token
    if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu header Authorization: Bearer <token>",
        )

    file_name = SAMPLE_FILES.get(body.problem_type)
    if file_name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không có dữ liệu mẫu cho problem_type '{body.problem_type}'. Hỗ trợ: {list(SAMPLE_FILES)}",
        )

    # Đọc lại file mỗi lần gọi để sửa JSON mẫu là thấy ngay
    with open(PROFILE_DIR / file_name, encoding="utf-8") as f:
        pipeline = json.load(f)

    if body.job_id is not None:
        pipeline["job_id"] = body.job_id

    return {
        "success": True,
        "message": "Lấy dữ liệu mẫu pipeline thành công!",
        "pipeline": pipeline,
    }
