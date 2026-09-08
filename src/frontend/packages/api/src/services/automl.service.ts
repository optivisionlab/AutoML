import { AxiosInstance } from "axios";
import {
  DataPreviewResponse,
  FeaturesResponse,
  MetricsResponse,
  StartTrainingPayload,
  StartTrainingResponse,
} from "@automl/domain";

export const createAutoMLService = (client: AxiosInstance) => ({
  getFeatures: async (datasetId: string, problemType: string): Promise<FeaturesResponse> => {
    const res = await client.get<FeaturesResponse>("/v2/auto/features", {
      params: {
        id_data: datasetId,
        problem_type: problemType,
      },
    });
    return res.data;
  },

  getDatasetPreview: async (datasetId: string): Promise<DataPreviewResponse> => {
    const res = await client.get<DataPreviewResponse>("/v2/auto/data", {
      params: {
        id_data: datasetId,
      },
    });
    return res.data;
  },

  getMetrics: async (problemType: string): Promise<MetricsResponse> => {
    const res = await client.get<MetricsResponse>("/v2/auto/metrics", {
      params: {
        problem_type: problemType,
      },
    });
    return res.data;
  },

  startTrainingJob: async (payload: StartTrainingPayload): Promise<StartTrainingResponse> => {
    const res = await client.post<StartTrainingResponse>("/v2/auto/jobs/training", payload);
    return res.data;
  },
});
