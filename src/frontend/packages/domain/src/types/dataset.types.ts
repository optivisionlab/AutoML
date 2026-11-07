import { BaseResponse, PaginatedResponse, UniversalFile } from "./common.types";

export interface Dataset {
  _id: string;
  dataName: string;
  dataType: string;
  createDate: number;
  latestUpdate?: number;
  lastestUpdate?: number;
  thumbnail?: string | null;
  description?: string | null;
  public?: boolean;
  userId?: string;
  username?: string;
  role?: string;
}

export interface AdminDatasetItem extends Dataset {
  userId: string;
  username: string;
  role: string;
}

export interface GetDatasetsParams {
  current_page?: number;
  page_size?: number;
  data_type?: string | null;
  sort_name?: "asc" | "desc" | string | null;
  sort_time?: "asc" | "desc" | string | null;
}

export interface DatasetUploadPayload {
  file: UniversalFile;
  dataName: string;
  dataType: "table" | "image" | "text" | string;
  description?: string | null;
  public?: boolean;
  thumbnail_file?: UniversalFile | null;
  userId?: string;
}

export interface DatasetUpdatePayload {
  datasetId: string;
  dataName?: string;
  description?: string | null;
  public?: boolean;
  thumbnail_file?: UniversalFile | null;
}

export interface DatasetFeaturesResponseData {
  features: Record<string, boolean>;
}

export interface DatasetDataPreviewResponseData {
  rows: number;
  data: Record<string, unknown>[];
}

export interface ProblemMetricsData {
  problem_type: string;
  metrics: string[];
}

export type ProblemMetricsResponse = BaseResponse<ProblemMetricsData>;

export interface GetProblemMetricsParams {
  problem_type?: "classification" | "regression" | "time_series" | string;
}

export interface DatasetTrainingConfig {
  choose?: string | null;
  problem_type: "classification" | "regression" | string;
  target: string;
  list_feature: string[];
  metric_sort: string;
  search_algorithm:
    | "tpe_search"
    | "bayesian_search"
    | "grid_search"
    | "random_search"
    | "genetic_algorithm"
    | string;
  timeout?: number | null;
}

export interface StartTrainingPayload {
  id: string;
  config: DatasetTrainingConfig;
}

export interface StartTrainingResponseData {
  job_id: string;
}

export type DatasetResponse = BaseResponse<Dataset>;
export type DatasetsListResponse = PaginatedResponse<Dataset>;
export type AdminDatasetsListResponse = PaginatedResponse<AdminDatasetItem>;
export type DatasetFeaturesResponse = BaseResponse<DatasetFeaturesResponseData>;
export type DatasetDataPreviewResponse = BaseResponse<DatasetDataPreviewResponseData>;
export type StartTrainingResponse = BaseResponse<StartTrainingResponseData>;

// Legacy compatibility aliases
export type DatasetFormPayload = {
  userId?: string;
  datasetId?: string;
  dataName?: string;
  dataType?: string;
  description?: string;
  public?: boolean;
  file?: UniversalFile | null;
  thumbnail_file?: UniversalFile | null;
};

// Database Connector (4.5, 4.6, 4.7)
export interface DatabaseConnection {
  db_type:
    | "postgres"
    | "postgresql"
    | "mysql"
    | "sqlite"
    | "sqlite3"
    | "duckdb"
    | "mssql"
    | "sqlserver"
    | "snowflake"
    | "bigquery"
    | "clickhouse"
    | "oracle"
    | "trino"
    | "presto"
    | "hive"
    | "redshift"
    | "amazon_redshift"
    | string;
  database: string;
  host?: string | null;
  port?: number | null;
  user?: string | null;
  password?: string | null;
  schema_name?: string | null;
  extra_params?: Record<string, unknown>;
}

export type ConnectDBPayload = DatabaseConnection;

export interface DatabaseConnectData {
  tables: string[];
}

export type ConnectDBResponse = BaseResponse<DatabaseConnectData> & {
  tables?: string[];
};

// 4.6 Database Table Info & Preview
export interface TableInfoRequest extends DatabaseConnection {
  table_name: string;
  limit?: number;
}

export interface TableColumnSchema {
  name: string;
  type: string;
}

export interface TableInfoData {
  table_name: string;
  columns: TableColumnSchema[];
  preview_data: Array<Record<string, unknown>>;
  preview_count: number;
}

export type TableInfoResponse = BaseResponse<TableInfoData>;

// 4.7 Database Table Import
export interface ImportDatabaseTablePayload extends DatabaseConnection {
  table_name: string;
  data_name: string;
  description?: string | null;
  public?: boolean;
}

export type ImportDatabaseTableResponse = BaseResponse<Dataset> & {
  dataset_id?: string;
};
