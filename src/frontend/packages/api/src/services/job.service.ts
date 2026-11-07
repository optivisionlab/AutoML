import { AxiosInstance } from "axios";
import {
  CancelJobResponse,
  JobsListParams,
  JobsListResponse,
  TrainingJob,
  GetPipelineSamplePayload,
  PipelineSampleResponse,
  PipelineData,
} from "@automl/domain";

export const createJobService = (client: AxiosInstance) => ({
  // 6.1 GET /api/v1/inference/jobs
  getJobs: async (params?: JobsListParams): Promise<JobsListResponse> => {
    const res = await client.get<JobsListResponse>("/api/v1/inference/jobs", {
      params: {
        current_page: params?.current_page ?? 1,
        page_size: params?.page_size ?? 10,
        sort_name: params?.sort_name || undefined,
        sort_time: params?.sort_time || "desc",
      },
    });
    if (res.data?.data) {
      res.data.data = res.data.data.map((job) => ({
        ...job,
        job_id: job.job_id || job._id,
      }));
    }
    return res.data;
  },

  // 6.2 POST /api/v1/inference/jobs/{id}/cancel
  cancelJob: async (jobId: string): Promise<CancelJobResponse> => {
    const res = await client.post<CancelJobResponse>(
      `/api/v1/inference/jobs/${jobId}/cancel`,
    );
    return res.data;
  },

  // Legacy compatibility methods
  getJobsOffset: async (params: any): Promise<unknown> => {
    const res = await client.get("/api/v1/inference/jobs", {
      params: { current_page: params?.page ?? 1, page_size: params?.limit ?? 10 },
    });
    return res.data;
  },

  getJobInfo: async (id: string): Promise<TrainingJob> => {
    const res = await client.get<any>(`/api/v1/inference/models/${id}/deployment`);
    return res.data?.data || res.data;
  },

  // GET /api/v1/inference/jobs/{job_id}/pipeline
  getJobPipeline: async (jobId: string): Promise<PipelineData> => {
    const res = await client.get<any>(`/api/v1/inference/jobs/${jobId}/pipeline`);
    return res.data?.data ?? res.data;
  },

  getLegacyJobsByUserId: async (_userId?: string): Promise<TrainingJob[]> => {
    const res = await client.get<JobsListResponse>("/api/v1/inference/jobs");
    return ((res.data?.data || []) as TrainingJob[]).map((job) => ({
      ...job,
      job_id: job.job_id || job._id,
    }));
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
