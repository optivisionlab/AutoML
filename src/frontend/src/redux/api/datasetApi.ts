import { baseApi } from "./baseApi";

// Dataset trả ra
export type Dataset = {
  _id: string;
  dataName: string;
  dataType: string;
  createDate: number;
  latestUpdate?: number;
  lastestUpdate?: number;
  userId: string;
  username?: string;
};

export type DatasetFormPayload = {
  userId?: string;
  datasetId?: string;
  dataName?: string;
  dataType?: string;
  file?: File | null;
};

const buildDatasetFormData = ({
  dataName,
  dataType,
  file,
}: DatasetFormPayload) => {
  const formData = new FormData();

  if (dataName) formData.append("data_name", dataName);
  if (dataType) formData.append("data_type", dataType);
  if (file) formData.append("file_data", file);

  return formData;
};

export const datasetApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Lấy các dataset có sẵn
    // API trả về một mảng Dataset[].
    // Khi gọi API, phải truyền vào một chuỗi string, chính là id.
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
      // tag cache riêng theo từng id.
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
} = datasetApi;
