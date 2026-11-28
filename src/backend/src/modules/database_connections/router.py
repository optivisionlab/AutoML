# Third-party Libraries
from fastapi import APIRouter, Body, Depends, Path, Query, status
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.config import databases
from src.core import dependencies, responses
from src.modules.database_connections.repository import ConnectionRepository
from src.modules.database_connections.schemas import (
    ConnectionCreate,
    ConnectionPublic,
    ConnectionUpdate,
    DescribeRequest,
    ImportRequest,
    ImportResult,
    PreviewRequest,
    PreviewResult,
)
from src.modules.database_connections.service import ConnectionService
from src.modules.datasets.repository import DatasetRepository
from src.modules.datasets.service import DatasetService


router = APIRouter(prefix="/database-connections", tags=["Database connections"])


def get_connection_service(db: AsyncDatabase = Depends(databases.get_db)) -> ConnectionService:
    return ConnectionService(ConnectionRepository(db), DatasetService(DatasetRepository(db)))


@router.post("", response_model=responses.BaseResponse[ConnectionPublic], status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: ConnectionCreate,
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(message="Database connection saved", data=await service.create_connection(current_user, payload))


@router.get("", response_model=responses.PaginatedResponse[ConnectionPublic])
async def list_connections(
    current_page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    items, meta = await service.list_connections(current_user, current_page, page_size)
    return responses.PaginatedResponse(message="Database connections", data=items, meta=responses.PaginationMeta(**meta))


@router.get("/{id}", response_model=responses.BaseResponse[ConnectionPublic])
async def get_connection(
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(data=await service.get_connection(current_user, id))


@router.patch("/{id}", response_model=responses.BaseResponse[ConnectionPublic])
async def update_connection(
    payload: ConnectionUpdate,
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(message="Database connection updated", data=await service.update_connection(current_user, id, payload))


@router.delete("/{id}", response_model=responses.BaseResponse[None])
async def delete_connection(
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    await service.delete_connection(current_user, id)
    return responses.BaseResponse(message="Database connection deleted", data=None)


@router.post("/{id}/test", response_model=responses.BaseResponse[dict])
async def test_connection(
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(data=await service.test_connection(current_user, id))


@router.get("/{id}/tables", response_model=responses.BaseResponse[dict])
async def list_tables(
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(data=await service.list_tables(current_user, id))


@router.post("/{id}/describe", response_model=responses.BaseResponse[dict])
async def describe_table(
    payload: DescribeRequest,
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(data=await service.describe_table(current_user, id, payload))


@router.post("/{id}/preview", response_model=responses.BaseResponse[PreviewResult])
async def preview_query(
    payload: PreviewRequest = Body(...),
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(data=await service.preview_query(current_user, id, payload.query.model_dump()))


@router.post("/{id}/import", response_model=responses.BaseResponse[ImportResult])
async def import_query(
    payload: ImportRequest,
    id: str = Path(..., description="Connection ID"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return responses.BaseResponse(message="Query result imported as dataset", data=await service.import_preview(current_user, id, payload))
