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
  ProblemMetricsResponse,
  TableInfoRequest,
  TableInfoResponse,
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

  // 3.2 GET /api/v1/datasets/metrics (Problem Metrics)
  getMetrics: async (
    problemType = "classification",
  ): Promise<ProblemMetricsResponse> => {
    const res = await client.get<ProblemMetricsResponse>(
      "/api/v1/datasets/metrics",
      {
        params: { problem_type: problemType },
      },
    );
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
    config: DatasetTrainingConfig | { config: DatasetTrainingConfig },
  ): Promise<StartTrainingResponse> => {
    const rawConfig = (config as any)?.config ? (config as any).config : config;
    let listFeature = (rawConfig as any).list_feature || (rawConfig as any).features || [];
    if (typeof listFeature === "string") {
      try {
        listFeature = JSON.parse(listFeature);
      } catch {
        listFeature = [listFeature];
      }
    }
    const bodyPayload = {
      choose: (rawConfig as any).choose || "new_model",
      problem_type: (rawConfig as any).problem_type || (rawConfig as any).problemType || "classification",
      target: (rawConfig as any).target,
      list_feature: Array.isArray(listFeature) ? listFeature : [],
      metric_sort: (rawConfig as any).metric_sort,
      search_algorithm: (rawConfig as any).search_algorithm || "bayesian_search",
      ...((rawConfig as any).timeout !== undefined ? { timeout: (rawConfig as any).timeout } : {}),
    };
    const res = await client.post<StartTrainingResponse>(
      `/api/v1/datasets/${id}/training`,
      bodyPayload,
    );
    return res.data;
  },

  // 4.5 POST /api/v1/datasets/database/connect
  connectDatabase: async (payload: ConnectDBPayload): Promise<ConnectDBResponse> => {
    try {
      const res = await client.post<ConnectDBResponse>("/api/v1/datasets/database/connect", payload);
      return res.data;
    } catch (err) {
      // Fallback for legacy backend route if not yet migrated
      try {
        const fallbackRes = await client.post<ConnectDBResponse>("/connect-database", payload);
        return fallbackRes.data;
      } catch {
        throw err;
      }
    }
  },

  // 4.6 POST /api/v1/datasets/database/table-info
  getTableInfo: async (payload: TableInfoRequest): Promise<TableInfoResponse> => {
    const res = await client.post<TableInfoResponse>(
      "/api/v1/datasets/database/table-info",
      payload,
    );
    return res.data;
  },

  // 4.7 POST /api/v1/datasets/database/import
  importDatabaseTable: async (
    payload: ImportDatabaseTablePayload,
  ): Promise<ImportDatabaseTableResponse> => {
    try {
      const res = await client.post<ImportDatabaseTableResponse>(
        "/api/v1/datasets/database/import",
        payload,
      );
      return res.data;
    } catch (err) {
      // Fallback for legacy backend route if not yet migrated
      try {
        const fallbackRes = await client.post<ImportDatabaseTableResponse>(
          "/import-database-table",
          payload,
        );
        return fallbackRes.data;
      } catch {
        throw err;
      }
    }
  },

  // Legacy compatibility methods
  getDatasetsByUserId: async (_id?: string): Promise<any> => {
    const endpoint = _id === "0" ? "/api/v1/datasets/default" : "/api/v1/datasets";
    const res = await client.get<DatasetsListResponse>(endpoint);
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
