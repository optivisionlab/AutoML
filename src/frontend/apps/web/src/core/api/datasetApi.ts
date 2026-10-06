import {
  type Dataset,
  type DatasetFormPayload,
  type ConnectDBPayload,
  type ConnectDBResponse,
  type ImportDatabaseTablePayload,
  type ImportDatabaseTableResponse,
} from "@automl/domain";
import { buildDatasetFormData } from "@automl/api";
import { baseApi } from "./baseApi";

export type {
  Dataset,
  DatasetFormPayload,
  ConnectDBPayload,
  ConnectDBResponse,
  ImportDatabaseTablePayload,
  ImportDatabaseTableResponse,
};

export const datasetApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Lấy các dataset có sẵn theo userId
    getDatasetsByUserId: builder.query<Dataset[], string>({
      query: (id) => ({
        url: "/get-list-data-by-userid",
        method: "POST",
        params: { id },
      }),
      providesTags: ["Dataset"],
    }),
    getDatasetInfo: builder.query<Dataset, string>({
      query: (id) => ({
        url: "/get-data-info",
        params: { id },
      }),
      providesTags: (_result, _error, id) => [{ type: "Dataset", id }],
    }),

    // Lấy các dataset của tất cả người dùng
    getAllUserDatasets: builder.query<Dataset[], void>({
      query: () => ({
        url: "/get-list-data-user",
      }),
      providesTags: ["Dataset"],
    }),
    getDataFromUci: builder.mutation<unknown, number>({
      query: (idData) => ({
        url: "/get-data-from-uci",
        method: "POST",
        params: { id_data: idData },
      }),
    }),
    uploadDataset: builder.mutation<unknown, DatasetFormPayload>({
      query: (payload) => ({
        url: "/upload-dataset",
        method: "POST",
        data: buildDatasetFormData(payload),
        params: { user_id: payload.userId },
      }),
      invalidatesTags: ["Dataset"],
    }),
    updateDataset: builder.mutation<unknown, DatasetFormPayload>({
      query: (payload) => ({
        url: `/update-dataset/${payload.datasetId}`,
        method: "PUT",
        data: buildDatasetFormData(payload),
      }),
      invalidatesTags: (_result, _error, payload) => [
        "Dataset",
        { type: "Dataset", id: payload.datasetId },
      ],
    }),

    // Xoá dataset
    deleteDataset: builder.mutation<unknown, string>({
      query: (datasetId) => ({
        url: `/delete-dataset/${datasetId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Dataset"],
    }),

    // Kết nối database và lấy danh sách bảng
    connectDatabase: builder.mutation<ConnectDBResponse, ConnectDBPayload>({
      query: (payload) => ({
        url: "/connect-database",
        method: "POST",
        data: payload,
      }),
    }),

    // Trích xuất bảng CSDL thành dataset trong AutoML
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
  }),
});

export const {
  useDeleteDatasetMutation,
  useGetAllUserDatasetsQuery,
  useGetDataFromUciMutation,
  useGetDatasetInfoQuery,
  useGetDatasetsByUserIdQuery,
  useUpdateDatasetMutation,
  useUploadDatasetMutation,
  useConnectDatabaseMutation,
  useImportDatabaseTableMutation,
} = datasetApi;
