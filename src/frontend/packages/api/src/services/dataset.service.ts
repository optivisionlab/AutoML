import { AxiosInstance } from "axios";
import {
  AdminDatasetsListResponse,
  BaseResponse,
  DatasetDataPreviewResponse,
  DatasetFeaturesResponse,
  DatasetResponse,
  DatasetsListResponse,
  DatasetTrainingConfig,
  DatasetUpdatePayload,
  DatasetUploadPayload,
  GetDatasetsParams,
  StartTrainingResponse,
  ConnectDBPayload,
  ConnectDBResponse,
  ImportDatabaseTablePayload,
  ImportDatabaseTableResponse,
} from "@automl/domain";
import {
  buildDatasetUploadFormData,
  buildDatasetUpdateFormData,
} from "../form-data";

export const createDatasetService = (client: AxiosInstance) => ({
  // 3.1 GET /api/v1/datasets
  getDatasets: async (params?: GetDatasetsParams): Promise<DatasetsListResponse> => {
    const res = await client.get<DatasetsListResponse>("/api/v1/datasets", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
        data_type: params?.data_type || undefined,
        sort_name: params?.sort_name || undefined,
        sort_time: params?.sort_time || "desc",
      },
    });
    return res.data;
  },

  // 3.2 GET /api/v1/datasets/default
  getDefaultDatasets: async (params?: GetDatasetsParams): Promise<DatasetsListResponse> => {
    const res = await client.get<DatasetsListResponse>("/api/v1/datasets/default", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
      },
    });
    return res.data;
  },

  // 3.3 GET /api/v1/datasets/all (Admin Only)
  getAllDatasets: async (params?: GetDatasetsParams): Promise<AdminDatasetsListResponse> => {
    const res = await client.get<AdminDatasetsListResponse>("/api/v1/datasets/all", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
      },
    });
    return res.data;
  },

  // 3.4 GET /api/v1/datasets/{id}
  getDatasetById: async (id: string): Promise<DatasetResponse> => {
    const res = await client.get<DatasetResponse>(`/api/v1/datasets/${id}`);
    return res.data;
  },

  // 3.5 POST /api/v1/datasets
  uploadDataset: async (payload: DatasetUploadPayload): Promise<DatasetResponse> => {
    const formData = buildDatasetUploadFormData(payload);
    const res = await client.post<DatasetResponse>("/api/v1/datasets", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  // 3.6 PUT /api/v1/datasets/{id}
  updateDataset: async (payload: DatasetUpdatePayload): Promise<DatasetResponse> => {
    const formData = buildDatasetUpdateFormData(payload);
    const res = await client.put<DatasetResponse>(
      `/api/v1/datasets/${payload.datasetId}`,
      formData,
      {
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    return res.data;
  },

  // 3.7 DELETE /api/v1/datasets/{id}
  deleteDataset: async (id: string): Promise<BaseResponse<null>> => {
    const res = await client.delete<BaseResponse<null>>(`/api/v1/datasets/${id}`);
    return res.data;
  },

  // 3.8 GET /api/v1/datasets/{id}/features
  getFeatures: async (
    id: string,
    problemType: "classification" | "regression" | string,
  ): Promise<DatasetFeaturesResponse> => {
    const res = await client.get<DatasetFeaturesResponse>(
      `/api/v1/datasets/${id}/features`,
      {
        params: { problem_type: problemType },
      },
    );
    return res.data;
  },

  // 3.9 GET /api/v1/datasets/{id}/data
  getDataPreview: async (
    id: string,
    numRows = 50,
  ): Promise<DatasetDataPreviewResponse> => {
    const res = await client.get<DatasetDataPreviewResponse>(
      `/api/v1/datasets/${id}/data`,
      {
        params: { num_rows: numRows },
      },
    );
    return res.data;
  },

  // 3.10 POST /api/v1/datasets/{id}/training
  startTraining: async (
    id: string,
    config: DatasetTrainingConfig,
  ): Promise<StartTrainingResponse> => {
    const res = await client.post<StartTrainingResponse>(
      `/api/v1/datasets/${id}/training`,
      { config },
    );
    return res.data;
  },

  // Database connector extension
  connectDatabase: async (payload: ConnectDBPayload): Promise<ConnectDBResponse> => {
    const res = await client.post<ConnectDBResponse>("/connect-database", payload);
    return res.data;
  },

  importDatabaseTable: async (
    payload: ImportDatabaseTablePayload,
  ): Promise<ImportDatabaseTableResponse> => {
    const res = await client.post<ImportDatabaseTableResponse>(
      "/import-database-table",
      payload,
    );
    return res.data;
  },

  // Legacy compatibility methods
  getDatasetsByUserId: async (_id?: string): Promise<any> => {
    const res = await client.get<DatasetsListResponse>("/api/v1/datasets");
    return res.data.data || res.data;
  },
  getDatasetInfo: async (id: string): Promise<any> => {
    const res = await client.get<DatasetResponse>(`/api/v1/datasets/${id}`);
    return res.data.data || res.data;
  },
  getAllUserDatasets: async (): Promise<any> => {
    const res = await client.get<AdminDatasetsListResponse>("/api/v1/datasets/all");
    return res.data.data || res.data;
  },
});
