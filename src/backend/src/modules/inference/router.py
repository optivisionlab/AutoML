# Third-party Libraries
from fastapi import APIRouter, Depends, Path, Query, Request, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.core import dependencies, responses
from src.config import databases
from src.modules.datasets import SortNameEnum, SortTimeEnum
from src.modules.inference.service import InferenceService
from src.modules.inference.schemas import (
    ModelActivationUpdate,
    DeploymentInfoResponse,
    PredictRequest,
    PredictResponse,
    JobItemResponse,
)


# Router Definition
router = APIRouter(prefix="/inference", tags=["Inference & Model Serving"])


def get_inference_service(db: AsyncDatabase = Depends(databases.get_db)) -> InferenceService:
    return InferenceService(db)


@router.get("/jobs", response_model=responses.PaginatedResponse[JobItemResponse])
async def get_list_jobs(
    current_page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_name: SortNameEnum | None = Query(None, description="Sort by dataset name (A-Z/Z-A)"),
    sort_time: SortTimeEnum | None = Query(SortTimeEnum.NEWEST, description="Sort by creation time"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Retrieve paginated list of all training jobs for the user (no filter on activate).
    """
    sort_name_value = sort_name.value if sort_name else None
    sort_time_value = sort_time.value if sort_time else None

    jobs, meta = await service.get_user_jobs(
        user_id=str(current_user["_id"]),
        current_page=current_page,
        page_size=page_size,
        activate=None,
        sort_name=sort_name_value,
        sort_time=sort_time_value,
        is_admin=(current_user.get("role") == "admin")
    )

    return responses.PaginatedResponse(
        message="Successfully retrieved the jobs list",
        data=jobs,
        meta=responses.PaginationMeta(**meta),
    )


@router.get("/models", response_model=responses.PaginatedResponse[JobItemResponse])
async def get_list_active_models(
    current_page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_name: SortNameEnum | None = Query(None, description="Sort by dataset name (A-Z/Z-A)"),
    sort_time: SortTimeEnum | None = Query(SortTimeEnum.NEWEST, description="Sort by creation time"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Retrieve paginated list of active/deployed models (filtered by activate=1).
    """
    sort_name_value = sort_name.value if sort_name else None
    sort_time_value = sort_time.value if sort_time else None

    models, meta = await service.get_user_jobs(
        user_id=str(current_user["_id"]),
        current_page=current_page,
        page_size=page_size,
        activate=1,
        sort_name=sort_name_value,
        sort_time=sort_time_value,
        is_admin=(current_user.get("role") == "admin")
    )

    return responses.PaginatedResponse(
        message="Successfully retrieved the active models list",
        data=models,
        meta=responses.PaginationMeta(**meta),
    )


@router.put("/models/{id}/activation", response_model=responses.BaseResponse[DeploymentInfoResponse])
async def toggle_model_activation(
    request: Request,
    id: str = Path(..., description="Training Job ID"),
    payload: ModelActivationUpdate = ...,
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Toggle model serving API deployment (1: Deploy/Activate, 0: Undeploy/Deactivate).
    """
    base_url = str(request.base_url)
    deployment_info = await service.toggle_model_activation(
        current_user=current_user,
        job_id=id,
        activate=payload.activate,
        base_url=base_url,
    )

    action_text = "activated and deployed" if payload.activate == 1 else "deactivated and undeployed"
    return responses.BaseResponse(
        message=f"Model successfully {action_text}",
        data=deployment_info,
    )


@router.get("/models/{id}/deployment", response_model=responses.BaseResponse[DeploymentInfoResponse])
async def get_model_deployment_info(
    request: Request,
    id: str = Path(..., description="Training Job ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Retrieve model deployment status, endpoint details, and 1-Click Code Snippets (cURL, Python, JS, C#, PHP).
    """
    base_url = str(request.base_url)
    deployment_info = await service.get_deployment_info(
        current_user=current_user,
        job_id=id,
        base_url=base_url,
    )

    return responses.BaseResponse(
        message="Model deployment details retrieved successfully",
        data=deployment_info,
    )


@router.post("/models/{id}/predict", response_model=responses.BaseResponse[PredictResponse])
async def predict_model(
    id: str = Path(..., description="Training Job ID"),
    payload: PredictRequest = ...,
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Execute real-time model predictions. Model must be active (activate=1).
    """
    result = await service.predict(
        current_user=current_user,
        job_id=id,
        request=payload,
    )

    return responses.BaseResponse(
        message="Prediction executed successfully",
        data=result,
    )


@router.post("/models/{id}/predict/file")
async def predict_file_and_download(
    id: str = Path(..., description="Training Job ID"),
    file: UploadFile = File(..., description="CSV or Excel file to run batch predictions on"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Upload a CSV or Excel dataset, execute batch predictions using the active model,
    and return the original file with a new prediction column as a StreamingResponse for direct download.
    """
    filename, media_type, output_buffer = await service.predict_file(
        current_user=current_user,
        job_id=id,
        file=file,
    )

    return StreamingResponse(
        output_buffer,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/models/{id}/export/notebook")
async def export_model_notebook(
    id: str = Path(..., description="Training Job ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Export full runnable Jupyter Notebook (.ipynb) for the trained AutoML model.
    """
    filename, content_bytes = await service.export_notebook(
        current_user=current_user,
        job_id=id,
    )

    return Response(
        content=content_bytes,
        media_type="application/x-ipynb+json",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/models/{id}/export/docker")
async def export_docker_package(
    id: str = Path(..., description="Training Job ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Export standalone Docker Microservice package (.zip) containing FastAPI server, Dockerfile, and model.
    """
    filename, content_bytes = await service.export_docker_package(
        current_user=current_user,
        job_id=id,
    )

    return Response(
        content=content_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/models/{id}/export/model")
async def export_model_binary(
    id: str = Path(..., description="Training Job ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: InferenceService = Depends(get_inference_service),
):
    """
    Download raw trained model artifact binary (.pkl).
    """
    filename, content_bytes = await service.export_model_binary(
        current_user=current_user,
        job_id=id,
    )

    return Response(
        content=content_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
