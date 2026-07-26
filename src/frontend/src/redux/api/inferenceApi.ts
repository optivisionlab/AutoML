import axios from "axios";
import { axiosClient, baseApi } from "./baseApi";

type PredictionFile = {
  blob: Blob;
  fileName: string;
};

const resolveFileName = (contentDisposition?: string) => {
  if (!contentDisposition) return "result.csv";

  const match =
    contentDisposition.match(/filename\*=UTF-8''(.+)/) ||
    contentDisposition.match(/filename="?([^"]+)"?/);

  return match?.[1] ? decodeURIComponent(match[1]) : "result.csv";
};

export const inferenceApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    inferenceModel: builder.mutation<unknown, { jobId: string; file: File }>({
      query: ({ jobId, file }) => {
        const formData = new FormData();
        formData.append("file_data", file);

        return {
          url: "/inference-model",
          method: "POST",
          data: formData,
          params: { job_id: jobId },
        };
      },
      invalidatesTags: ["Inference"],
    }),
    cancelPrediction: builder.mutation<unknown, string>({
      query: (jobId) => ({
        url: `/v2/auto/${jobId}/predictions`,
        method: "DELETE",
      }),
      invalidatesTags: ["Inference"],
    }),
    runPrediction: builder.mutation<PredictionFile, { jobId: string; file: File }>({
      async queryFn({ jobId, file }) {
        const formData = new FormData();
        formData.append("file_data", file);

        try {
          const response = await axiosClient.post(
            `/v2/auto/${jobId}/predictions`,
            formData,
            { responseType: "blob" },
          );

          return {
            data: {
              blob: response.data,
              fileName: resolveFileName(response.headers["content-disposition"]),
            },
          };
        } catch (error) {
          if (axios.isAxiosError(error)) {
            return {
              error: {
                status: error.response?.status,
                data: error.response?.data ?? error.message,
              },
            };
          }

          return { error: { data: "Prediction failed" } };
        }
      },
      invalidatesTags: ["Inference"],
    }),
    activateModel: builder.mutation<
      unknown,
      { jobId: string; activate?: 0 | 1 }
    >({
      query: ({ jobId, activate = 1 }) => ({
        url: "/activate-model",
        method: "POST",
        params: {
          job_id: jobId,
          activate,
        },
      }),
      invalidatesTags: ["Job"],
    }),
  }),
});

export const {
  useActivateModelMutation,
  useCancelPredictionMutation,
  useInferenceModelMutation,
  useRunPredictionMutation,
} = inferenceApi;
