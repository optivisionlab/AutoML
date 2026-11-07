import {
  type AdminDatasetsListResponse,
  type BaseResponse,
  type ConnectDBPayload,
  type ConnectDBResponse,
  type Dataset,
  type DatasetDataPreviewResponse,
  type DatasetFeaturesResponse,
  type DatasetFormPayload,
  type DatasetResponse,
  type DatasetsListResponse,
  type DatasetTrainingConfig,
  type DatasetUpdatePayload,
  type DatasetUploadPayload,
  type GetDatasetsParams,
  type ImportDatabaseTablePayload,
  type ImportDatabaseTableResponse,
  type ProblemMetricsResponse,
  type GetProblemMetricsParams,
  type TableInfoRequest,
  type TableInfoResponse,
  type TableInfoData,
  type TableColumnSchema,
  type StartTrainingPayload,
  type StartTrainingResponse,
} from "@automl/domain";
import {
  buildDatasetUploadFormData,
  buildDatasetUpdateFormData,
} from "@automl/api";
import { baseApi } from "./baseApi";

export type {
  AdminDatasetsListResponse,
  BaseResponse,
  ConnectDBPayload,
  ConnectDBResponse,
  Dataset,
  DatasetDataPreviewResponse,
  DatasetFeaturesResponse,
  DatasetFormPayload,
  DatasetResponse,
  DatasetsListResponse,
  DatasetTrainingConfig,
  DatasetUpdatePayload,
  DatasetUploadPayload,
  GetDatasetsParams,
  ImportDatabaseTablePayload,
  ImportDatabaseTableResponse,
  ProblemMetricsResponse,
  GetProblemMetricsParams,
  TableInfoRequest,
  TableInfoResponse,
  TableInfoData,
  TableColumnSchema,
  StartTrainingPayload,
  StartTrainingResponse,
};

export const datasetApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // 3.1 GET /api/v1/datasets
    getDatasets: builder.query<DatasetsListResponse, GetDatasetsParams | void>({
      query: (params) => ({
        url: "/api/v1/datasets",
        params: {
          current_page: params?.current_page ?? 1,
          page_size: params?.page_size ?? 10,
          data_type: params?.data_type || undefined,
          sort_name: params?.sort_name || undefined,
          sort_time: params?.sort_time || "desc",
        },
      }),
      providesTags: ["Dataset"],
    }),

    // 4.2 GET /api/v1/datasets/metrics (Problem Metrics)
    getProblemMetrics: builder.query<
      ProblemMetricsResponse,
      GetProblemMetricsParams | { problem_type?: string } | string | void
    >({
      query: (arg) => {
        const problemType = typeof arg === "string" ? arg : arg?.problem_type ?? "classification";
        return {
          url: "/api/v1/datasets/metrics",
          params: { problem_type: problemType },
        };
      },
      providesTags: (_result, _error, arg) => {
        const problemType = typeof arg === "string" ? arg : arg?.problem_type ?? "classification";
        return [{ type: "Dataset", id: `metrics-${problemType}` }];
      },
    }),

    // 4.3 GET /api/v1/datasets/default
    getDefaultDatasets: builder.query<DatasetsListResponse, GetDatasetsParams | void>({
      query: (params) => ({
        url: "/api/v1/datasets/default",
        params: {
          current_page: params?.current_page ?? 1,
          page_size: params?.page_size ?? 10,
        },
      }),
      providesTags: ["Dataset"],
    }),

    // 3.3 GET /api/v1/datasets/all (Admin Only)
    getAllDatasets: builder.query<AdminDatasetsListResponse, GetDatasetsParams | void>({
      query: (params) => ({
        url: "/api/v1/datasets/all",
        params: {
          current_page: params?.current_page ?? 1,
          page_size: params?.page_size ?? 10,
        },
      }),
      providesTags: ["Dataset"],
    }),

    // 3.4 GET /api/v1/datasets/{id}
    getDatasetInfo: builder.query<DatasetResponse, string>({
      query: (id) => ({
        url: `/api/v1/datasets/${id}`,
      }),
      providesTags: (_result, _error, id) => [{ type: "Dataset", id }],
    }),

    // 3.5 POST /api/v1/datasets
    uploadDataset: builder.mutation<DatasetResponse, DatasetUploadPayload | any>({
      query: (payload) => ({
        url: "/api/v1/datasets",
        method: "POST",
        data: buildDatasetUploadFormData(payload),
      }),
      invalidatesTags: ["Dataset"],
    }),

    // 3.6 PUT /api/v1/datasets/{id}
    updateDataset: builder.mutation<
      DatasetResponse,
      DatasetUpdatePayload | any
    >({
      query: (payload) => ({
        url: `/api/v1/datasets/${payload.datasetId || payload.id}`,
        method: "PUT",
        data: buildDatasetUpdateFormData(payload),
      }),
      invalidatesTags: (_result, _error, payload) => [
        "Dataset",
        { type: "Dataset", id: payload.datasetId || payload.id },
      ],
    }),

    // 3.7 DELETE /api/v1/datasets/{id}
    deleteDataset: builder.mutation<BaseResponse<null>, string>({
      query: (datasetId) => ({
        url: `/api/v1/datasets/${datasetId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Dataset"],
    }),

    // 3.8 GET /api/v1/datasets/{id}/features
    getDatasetFeatures: builder.query<
      DatasetFeaturesResponse,
      { datasetId: string; problemType: string }
    >({
      query: ({ datasetId, problemType }) => ({
        url: `/api/v1/datasets/${datasetId}/features`,
        params: { problem_type: problemType },
      }),
      transformResponse: (response: any): DatasetFeaturesResponse => {
        const raw = response?.data?.features ?? response?.data ?? response?.features ?? response;
        const featuresMap: Record<string, boolean> = {};

        if (Array.isArray(raw)) {
          raw.forEach((col: string) => {
            featuresMap[col] = true;
          });
        } else if (raw && typeof raw === "object") {
          Object.entries(raw).forEach(([k, v]) => {
            if (k !== "success" && k !== "message" && k !== "status" && k !== "meta") {
              featuresMap[k] = Boolean(v);
            }
          });
        }

        return {
          success: true,
          message: response?.message || "Features retrieved successfully",
          data: { features: featuresMap },
        };
      },
      providesTags: (_result, _error, { datasetId }) => [
        { type: "Dataset", id: `features-${datasetId}` },
      ],
    }),

    // 3.9 GET /api/v1/datasets/{id}/data
    getDatasetDataPreview: builder.query<
      DatasetDataPreviewResponse,
      { datasetId: string; numRows?: number } | string
    >({
      query: (arg) => {
        const datasetId = typeof arg === "string" ? arg : arg.datasetId;
        const numRows = typeof arg === "object" ? arg.numRows : 50;
        return {
          url: `/api/v1/datasets/${datasetId}/data`,
          params: { num_rows: numRows ?? 50 },
        };
      },
      providesTags: (_result, _error, arg) => {
        const datasetId = typeof arg === "string" ? arg : arg.datasetId;
        return [{ type: "Dataset", id: `data-${datasetId}` }];
      },
    }),

    // 4.14 POST /api/v1/datasets/{id}/training
    startDatasetTraining: builder.mutation<
      StartTrainingResponse,
      { id: string; config: DatasetTrainingConfig | any }
    >({
      query: ({ id, config }) => {
        const rawConfig = (config as any)?.config ? (config as any).config : config;
        let listFeature = rawConfig.list_feature || rawConfig.features || [];
        if (typeof listFeature === "string") {
          try {
            listFeature = JSON.parse(listFeature);
          } catch {
            listFeature = [listFeature];
          }
        }

        const body = {
          choose: rawConfig.choose || "new_model",
          problem_type: rawConfig.problem_type || rawConfig.problemType || "classification",
          target: rawConfig.target,
          list_feature: Array.isArray(listFeature) ? listFeature : [],
          metric_sort: rawConfig.metric_sort,
          search_algorithm: rawConfig.search_algorithm || "bayesian_search",
          ...(rawConfig.timeout !== undefined ? { timeout: rawConfig.timeout } : {}),
        };

        return {
          url: `/api/v1/datasets/${id}/training`,
          method: "POST",
          data: body,
        };
      },
      invalidatesTags: ["Job", "Inference"],
    }),

    // 4.5 POST /api/v1/datasets/database/connect
    connectDatabase: builder.mutation<ConnectDBResponse, ConnectDBPayload>({
      query: (payload) => ({
        url: "/api/v1/datasets/database/connect",
        method: "POST",
        data: payload,
      }),
    }),

    // 4.6 POST /api/v1/datasets/database/table-info
    getTableInfo: builder.mutation<TableInfoResponse, TableInfoRequest>({
      query: (payload) => ({
        url: "/api/v1/datasets/database/table-info",
        method: "POST",
        data: payload,
      }),
    }),

    // 4.7 POST /api/v1/datasets/database/import
    importDatabaseTable: builder.mutation<
      ImportDatabaseTableResponse,
      ImportDatabaseTablePayload
    >({
      query: (payload) => ({
        url: "/api/v1/datasets/database/import",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Dataset"],
    }),

    // Legacy hook compatibility
    getDatasetsByUserId: builder.query<Dataset[], string | void>({
      query: (userId) => ({
        url: userId === "0" ? "/api/v1/datasets/default" : "/api/v1/datasets",
        params: { current_page: 1, page_size: 100 },
      }),
      transformResponse: (response: DatasetsListResponse) => response.data || [],
      providesTags: ["Dataset"],
    }),

    getAllUserDatasets: builder.query<Dataset[], void>({
      query: () => ({
        url: "/api/v1/datasets/all",
        params: { current_page: 1, page_size: 100 },
      }),
      transformResponse: (response: AdminDatasetsListResponse) => response.data || [],
      providesTags: ["Dataset"],
    }),
  }),
});

export const {
  useConnectDatabaseMutation,
  useDeleteDatasetMutation,
  useGetAllDatasetsQuery,
  useGetAllUserDatasetsQuery,
  useGetDatasetDataPreviewQuery,
  useGetDatasetFeaturesQuery,
  useGetDatasetInfoQuery,
  useGetDatasetsByUserIdQuery,
  useGetDatasetsQuery,
  useGetDefaultDatasetsQuery,
  useGetProblemMetricsQuery,
  useGetTableInfoMutation,
  useImportDatabaseTableMutation,
  useLazyGetDatasetDataPreviewQuery,
  useLazyGetDatasetFeaturesQuery,
  useLazyGetDatasetInfoQuery,
  useLazyGetDatasetsQuery,
  useLazyGetDefaultDatasetsQuery,
  useLazyGetProblemMetricsQuery,
  useStartDatasetTrainingMutation,
  useUpdateDatasetMutation,
  useUploadDatasetMutation,
} = datasetApi;
