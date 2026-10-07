# Third-party Libraries
from fastapi import APIRouter, Depends
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.core import dependencies, responses
from src.config import databases
from src.modules.connectors.schemas import DatabaseConnection, TableInfoRequest, ImportTableRequest
from src.modules.connectors.service import ConnectorService
from src.modules.datasets.repository import DatasetRepository
from src.modules.datasets.schemas import DatasetResponse


# Router
router = APIRouter(prefix="/connectors/database", tags=["Database Connectors"])

def get_connector_service(db: AsyncDatabase = Depends(databases.get_db)) -> ConnectorService:
    return ConnectorService(DatasetRepository(db))


@router.post("/connect", response_model=responses.BaseResponse[dict])
async def connect_database(
    payload: DatabaseConnection,
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectorService = Depends(get_connector_service),
):
    tables = await service.connect(payload)

    return responses.BaseResponse(
        message="Database connection successful",
        data={"tables": tables},
    )


@router.post("/table-info", response_model=responses.BaseResponse[dict])
async def get_table_info(
    payload: TableInfoRequest,
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectorService = Depends(get_connector_service),
):
    info = await service.get_table_info(payload)

    return responses.BaseResponse(
        message=f"Successfully retrieved information of table '{payload.table_name}'",
        data=info,
    )


@router.post("/import", response_model=responses.BaseResponse[DatasetResponse])
async def import_database_table(
    payload: ImportTableRequest,
    current_user: dict = Depends(dependencies.get_current_user),
    service: ConnectorService = Depends(get_connector_service),
):
    dataset = await service.import_table(current_user=current_user, req=payload)

    return responses.BaseResponse(
        message=f"Table '{payload.table_name}' imported successfully",
        data=dataset,
    )
