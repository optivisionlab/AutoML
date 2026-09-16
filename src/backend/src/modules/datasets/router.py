# Standard Libraries

# Third-party Libraries
from fastapi import APIRouter, UploadFile, Depends, Query, Path, File, Form
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.config.database import get_db
from src.core.dependencies import get_current_user, require_admin
from src.core.responses import BaseResponse, PaginatedResponse, PaginationMeta
from src.modules.datasets.schemas import DatasetResponse, DataTypeEnum, SortNameEnum, SortTimeEnum, DatasetAdminResponse, DatasetCreate, DatasetUpdate
from src.modules.datasets.repository import DatasetRepository
from src.modules.datasets.service import DatasetService


# Router
router = APIRouter(prefix="/datasets", tags=["Datasets"])

def get_dataset_service(db: AsyncDatabase = Depends(get_db)) -> DatasetRepository:
    return DatasetService(DatasetRepository(db))


@router.get("", response_model=PaginatedResponse[DatasetResponse])
async def get_list_datasets(
    current_page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    data_type: DataTypeEnum | None = Query(None, description="Filter by data format"),
    sort_name: SortNameEnum | None = Query(None, description="Sort by name (A-Z/Z-A)"),
    sort_time: SortTimeEnum | None = Query(SortTimeEnum.NEWEST, description="Schedule (Last updated)"),
    current_user: dict = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service)
):
    data_type_value = data_type.value if data_type else None
    sort_name_value = sort_name.value if sort_name else None
    sort_time_value = sort_time.value if sort_time else None

    datasets, meta = await service.get_user_datasets(
        user_id=current_user["_id"],
        current_page=current_page,
        page_size=page_size,
        data_type=data_type_value,
        sort_name=sort_name_value,
        sort_time=sort_time_value
    )

    return PaginatedResponse(
        message="Successfully retrieved the data list",
        data=datasets,
        meta=PaginationMeta(**meta)
    )


@router.get("/default", dependencies=[Depends(get_current_user)], response_model=PaginatedResponse[DatasetResponse])
async def get_list_datasets(
    current_page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    data_type: DataTypeEnum | None = Query(None, description="Filter by data format"),
    sort_name: SortNameEnum | None = Query(None, description="Sort by name (A-Z/Z-A)"),
    sort_time: SortTimeEnum | None = Query(SortTimeEnum.NEWEST, description="Schedule (Last updated)"),
    service: DatasetService = Depends(get_dataset_service)
):
    data_type_value = data_type.value if data_type else None
    sort_name_value = sort_name.value if sort_name else None
    sort_time_value = sort_time.value if sort_time else None

    datasets, meta = await service.get_user_datasets(
        user_id="0",
        current_page=current_page,
        page_size=page_size,
        data_type=data_type_value,
        sort_name=sort_name_value,
        sort_time=sort_time_value
    )

    return PaginatedResponse(
        message="Successfully retrieved the data list",
        data=datasets,
        meta=PaginationMeta(**meta)
    )


@router.get("/all", dependencies=[Depends(require_admin)], response_model=PaginatedResponse[DatasetAdminResponse])
async def get_all_datasets_for_admin(
    current_page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    data_type: DataTypeEnum | None = Query(None, description="Filter by data format"),
    sort_name: SortNameEnum | None = Query(None, description="Sort by name (A-Z/Z-A)"),
    sort_time: SortTimeEnum | None = Query(SortTimeEnum.NEWEST, description="Schedule (Last updated)"),
    service: DatasetService = Depends(get_dataset_service)
):
    data_type_value = data_type.value if data_type else None
    sort_name_value = sort_name.value if sort_name else None
    sort_time_value = sort_time.value if sort_time else None

    datasets, meta = await service.get_all_datasets(
        current_page=current_page,
        page_size=page_size,
        data_type=data_type_value,
        sort_name=sort_name_value,
        sort_time=sort_time_value
    )

    return PaginatedResponse(
        message="Successfully retrieved all datasets for administration",
        data=datasets,
        meta=PaginationMeta(**meta)
    )


@router.get("/{id}", response_model=BaseResponse[DatasetResponse])
async def get_dataset_by_id(
    id: str = Path(..., description="Dataset ID"),
    current_user: dict = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service)
):
    dataset = await service.get_dataset_detail(
        user_id=current_user["_id"],
        dataset_id=id
    )

    return BaseResponse(
        message="Successfully retrieved dataset details",
        data=dataset
    )


@router.post("", response_model=BaseResponse[DatasetResponse])
async def upload_new_dataset(
    file: UploadFile = File(...),
    thumbnail_file: UploadFile | None = File(None, description="Image"),
    dataName: str = Form(...),
    dataType: DataTypeEnum = Form(...),
    description: str | None = Form(None),
    current_user: dict = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service)
):
    payload = DatasetCreate(
        dataName=dataName,
        dataType=dataType,
        description=description
    )

    dataset = await service.upload_and_process_dataset(
        current_user=current_user,
        payload=payload,
        file=file,
        thumbnail_file=thumbnail_file
    )

    return BaseResponse(
        message="Data upload and processing successful",
        data=dataset
    )


@router.put("/{id}", response_model=BaseResponse[DatasetResponse])
async def update_dataset(
    id: str = Path(..., description="Dataset ID"),
    dataName: str | None = Form(None),
    description: str | None = Form(None),
    thumbnail_file: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service)
):
    payload = DatasetUpdate(
        dataName=dataName,
        description=description
    )

    dataset = await service.update_dataset_info(
        user_id=current_user["_id"],
        dataset_id=id,
        payload=payload,
        thumbnail_file=thumbnail_file
    )

    return BaseResponse(
        message="Dataset information updated successfully",
        data=dataset
    )


@router.delete("/{id}", response_model=BaseResponse[None])
async def delete_dataset(
    id: str = Path(..., description="Dataset ID"),
    current_user: dict = Depends(get_current_user),
    service: DatasetService = Depends(get_dataset_service)
):
    await service.delete_dataset(
        current_user=current_user,
        dataset_id=id
    )

    return BaseResponse(
        message="Dataset deleted successfully",
        data=None
    )
