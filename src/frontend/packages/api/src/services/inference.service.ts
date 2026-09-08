import { AxiosInstance } from "axios";
import {
  ActivateModelPayload,
  InferencePayload,
  PredictionFile,
} from "@automl/domain";
import { appendUniversalFile } from "../form-data";
import { resolveFileName } from "../client";

export const createInferenceService = (client: AxiosInstance) => ({
  inferenceModel: async ({ jobId, file }: InferencePayload): Promise<unknown> => {
    const formData = new FormData();
    appendUniversalFile(formData, "file_data", file);

    const res = await client.post("/inference-model", formData, {
      params: { job_id: jobId },
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  cancelPrediction: async (jobId: string): Promise<unknown> => {
    const res = await client.delete(`/v2/auto/${jobId}/predictions`);
    return res.data;
  },

  runPrediction: async ({ jobId, file }: InferencePayload): Promise<PredictionFile> => {
    const formData = new FormData();
    appendUniversalFile(formData, "file_data", file);

    const res = await client.post(`/v2/auto/${jobId}/predictions`, formData, {
      responseType: "blob",
      headers: { "Content-Type": "multipart/form-data" },
    });

    return {
      blob: res.data,
      fileName: resolveFileName(res.headers["content-disposition"]),
    };
  },

  activateModel: async ({ jobId, activate = 1 }: ActivateModelPayload): Promise<unknown> => {
    const res = await client.post("/activate-model", null, {
      params: {
        job_id: jobId,
        activate,
      },
    });
    return res.data;
  },
});
