import { AxiosInstance } from "axios";
import {
  ActivateModelPayload,
  ActiveModelsResponse,
  DeploymentInfoResponse,
  JobsListParams,
  JobsListResponse,
  PredictionFile,
  RealtimePredictPayload,
  RealtimePredictResponse,
  UniversalFile,
} from "@automl/domain";
import { appendUniversalFile } from "../form-data";
import { resolveFileName } from "../client";

export const createInferenceService = (client: AxiosInstance) => ({
  // 5.1 GET /api/v1/inference/jobs
  getJobs: async (params?: JobsListParams): Promise<JobsListResponse> => {
    const res = await client.get<JobsListResponse>("/api/v1/inference/jobs", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
        sort_name: params?.sort_name || undefined,
        sort_time: params?.sort_time || "desc",
      },
    });
    return res.data;
  },

  // 5.2 GET /api/v1/inference/models
  getActiveModels: async (params?: JobsListParams): Promise<ActiveModelsResponse> => {
    const res = await client.get<ActiveModelsResponse>("/api/v1/inference/models", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
      },
    });
    return res.data;
  },

  // 5.3 PUT /api/v1/inference/models/{id}/activation
  setActivation: async ({
    jobId,
    activate,
  }: ActivateModelPayload): Promise<DeploymentInfoResponse> => {
    const res = await client.put<DeploymentInfoResponse>(
      `/api/v1/inference/models/${jobId}/activation`,
      { activate },
    );
    return res.data;
  },

  // 5.4 GET /api/v1/inference/models/{id}/deployment
  getDeploymentInfo: async (jobId: string): Promise<DeploymentInfoResponse> => {
    const res = await client.get<DeploymentInfoResponse>(
      `/api/v1/inference/models/${jobId}/deployment`,
    );
    return res.data;
  },

  // 5.5 POST /api/v1/inference/models/{id}/predict
  predictRealtime: async ({
    jobId,
    data,
  }: RealtimePredictPayload): Promise<RealtimePredictResponse> => {
    const res = await client.post<RealtimePredictResponse>(
      `/api/v1/inference/models/${jobId}/predict`,
      { data },
    );
    return res.data;
  },

  // 5.6 POST /api/v1/inference/models/{id}/predict/file
  predictBatchFile: async (
    jobId: string,
    file: UniversalFile,
  ): Promise<PredictionFile> => {
    const formData = new FormData();
    appendUniversalFile(formData, "file", file);

    const res = await client.post(
      `/api/v1/inference/models/${jobId}/predict/file`,
      formData,
      {
        responseType: "blob",
        headers: { "Content-Type": "multipart/form-data" },
      },
    );

    return {
      blob: res.data,
      fileName: resolveFileName(
        res.headers["content-disposition"],
        "predicted_result.csv",
      ),
    };
  },

  // 5.7 GET /api/v1/inference/models/{id}/export/notebook
  exportNotebook: async (jobId: string): Promise<PredictionFile> => {
    const res = await client.get(
      `/api/v1/inference/models/${jobId}/export/notebook`,
      { responseType: "blob" },
    );
    return {
      blob: res.data,
      fileName: resolveFileName(
        res.headers["content-disposition"],
        `hautoml_pipeline_${jobId}.ipynb`,
      ),
    };
  },

  // 5.8 GET /api/v1/inference/models/{id}/export/docker
  exportDocker: async (jobId: string): Promise<PredictionFile> => {
    const res = await client.get(
      `/api/v1/inference/models/${jobId}/export/docker`,
      { responseType: "blob" },
    );
    return {
      blob: res.data,
      fileName: resolveFileName(
        res.headers["content-disposition"],
        `hautoml_docker_${jobId}.zip`,
      ),
    };
  },

  // 5.9 GET /api/v1/inference/models/{id}/export/model
  exportModel: async (jobId: string): Promise<PredictionFile> => {
    const res = await client.get(
      `/api/v1/inference/models/${jobId}/export/model`,
      { responseType: "blob" },
    );
    return {
      blob: res.data,
      fileName: resolveFileName(
        res.headers["content-disposition"],
        `model_${jobId}.pkl`,
      ),
    };
  },

  // Legacy method compatibility aliases
  activateModel: async ({ jobId, activate = 1 }: any): Promise<any> => {
    const res = await client.put<DeploymentInfoResponse>(
      `/api/v1/inference/models/${jobId}/activation`,
      { activate },
    );
    return res.data;
  },
  runPrediction: async ({ jobId, file }: any): Promise<PredictionFile> => {
    const formData = new FormData();
    appendUniversalFile(formData, "file", file);
    const res = await client.post(
      `/api/v1/inference/models/${jobId}/predict/file`,
      formData,
      {
        responseType: "blob",
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    return {
      blob: res.data,
      fileName: resolveFileName(
        res.headers["content-disposition"],
        "predicted_result.csv",
      ),
    };
  },
  inferenceModel: async ({ jobId, file }: any): Promise<any> => {
    const formData = new FormData();
    appendUniversalFile(formData, "file", file);
    const res = await client.post(
      `/api/v1/inference/models/${jobId}/predict/file`,
      formData,
      {
        responseType: "blob",
        headers: { "Content-Type": "multipart/form-data" },
      },
    );
    return res.data;
  },
  cancelPrediction: async (_jobId: string): Promise<any> => {
    return { success: true };
  },
});
