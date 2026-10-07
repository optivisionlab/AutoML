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

    // 3.2 GET /api/v1/datasets/default
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

    // 3.10 POST /api/v1/datasets/{id}/training
    startDatasetTraining: builder.mutation<
      StartTrainingResponse,
      { id: string; config: DatasetTrainingConfig }
    >({
      query: ({ id, config }) => ({
        url: `/api/v1/datasets/${id}/training`,
        method: "POST",
        data: { config },
      }),
      invalidatesTags: ["Job", "Inference"],
    }),

    // External Database connector endpoints
    connectDatabase: builder.mutation<ConnectDBResponse, ConnectDBPayload>({
      query: (payload) => ({
        url: "/connect-database",
        method: "POST",
        data: payload,
      }),
    }),

    importDatabaseTable: builder.mutation<
      ImportDatabaseTableResponse,
      ImportDatabaseTablePayload
    >({
      query: (payload) => ({
        url: "/import-database-table",
        method: "POST",
        data: payload,
      }),
      invalidatesTags: ["Dataset"],
    }),

    // Legacy hook compatibility
    getDatasetsByUserId: builder.query<Dataset[], string | void>({
      query: () => ({
        url: "/api/v1/datasets",
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
  useImportDatabaseTableMutation,
  useLazyGetDatasetDataPreviewQuery,
  useLazyGetDatasetFeaturesQuery,
  useLazyGetDatasetInfoQuery,
  useLazyGetDatasetsQuery,
  useLazyGetDefaultDatasetsQuery,
  useStartDatasetTrainingMutation,
  useUpdateDatasetMutation,
  useUploadDatasetMutation,
} = datasetApi;
