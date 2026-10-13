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

export interface DatasetTrainingConfig {
  choose?: string | null;
  problem_type: "classification" | "regression" | string;
  target: string;
  list_feature: string[];
  metric_sort: string;
  search_algorithm:
    | "bayesian_search"
    | "grid_search"
    | "random_search"
    | "genetic_algorithm"
    | string;
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

export interface ConnectDBPayload {
  db_type: string;
  database: string;
  host?: string;
  port?: number | null;
  user?: string;
  password?: string;
  schema_name?: string;
  extra_params?: Record<string, unknown>;
}

export interface ConnectDBResponse {
  success: boolean;
  message: string;
  tables: string[];
}

export interface ImportDatabaseTablePayload {
  db_type: string;
  database: string;
  table_name: string;
  data_name: string;
  host?: string;
  port?: number | null;
  user?: string;
  password?: string;
  schema_name?: string;
  extra_params?: Record<string, unknown>;
}

export interface ImportDatabaseTableResponse {
  success: boolean;
  message: string;
  dataset_id?: string;
}
