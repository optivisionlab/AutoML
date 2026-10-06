import { AxiosInstance } from "axios";
import {
  GetJobsOffsetParams,
  TrainingJob,
  GetPipelineSamplePayload,
  PipelineSampleResponse,
} from "@automl/domain";

export const createJobService = (client: AxiosInstance) => ({
  getJobsOffset: async ({
    userId,
    page = 1,
    limit = 5,
  }: GetJobsOffsetParams): Promise<unknown> => {
    const res = await client.get(`/v2/auto/jobs/offset/${userId}`, {
      params: { page, limit },
    });
    return res.data;
  },

  getJobInfo: async (id: string): Promise<TrainingJob> => {
    const res = await client.post<TrainingJob>("/get-job-info", null, {
      params: { id },
    });
    return res.data;
  },

  getLegacyJobsByUserId: async (userId: string): Promise<TrainingJob[]> => {
    const res = await client.post<TrainingJob[]>("/get-list-job-by-userId", null, {
      params: { user_id: userId },
    });
    return res.data;
  },

  getPipelineSample: async (
    payload: GetPipelineSamplePayload,
  ): Promise<PipelineSampleResponse> => {
    const res = await client.post<PipelineSampleResponse>(
      "/get-pipeline-sample",
      payload,
    );
    return res.data;
  },
});

