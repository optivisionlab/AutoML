from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from .base import BaseDatabaseAdapter, DatabaseConfig


class BigQueryAdapter(BaseDatabaseAdapter):
    """Adapter kết nối Google BigQuery qua sqlalchemy-bigquery."""

    def __init__(self, config: DatabaseConfig):
        super().__init__(config)

    def get_connection_url(self) -> str:
        # BigQuery xác định theo project_id và dataset_id
        project_id = (
            self.config.extra_params.get("project_id")
            or (self.config.host if self.config.host and self.config.host != "localhost" else None)
            or self.config.database
        )
        dataset_id = (
            self.config.schema_name
            or self.config.extra_params.get("dataset_id")
            or (self.config.database if project_id != self.config.database else None)
        )

        if dataset_id and dataset_id != project_id:
            return f"bigquery://{project_id}/{dataset_id}"
        return f"bigquery://{project_id}"

    def create_engine(self) -> Engine:
        url = self.get_connection_url()
        cred_file = (
            self.config.extra_params.get("cred_file_path")
            or self.config.extra_params.get("credentials_path")
        )
        if cred_file:
            return create_engine(url, credentials_path=cred_file)
        return create_engine(url)

    def quote_identifier(self, identifier: str) -> str:
        escaped = identifier.replace('`', '\\`')
        return f"`{escaped}`"
