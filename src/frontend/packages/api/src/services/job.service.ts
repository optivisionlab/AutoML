import { AxiosInstance } from "axios";
import {
  CancelJobResponse,
  JobDetailPayload,
  JobDetailResponse,
  JobsListParams,
  JobsListResponse,
  PipelineData,
  TrainingJob,
  GetPipelineSamplePayload,
  PipelineSampleResponse,
} from "@automl/domain";

const unwrapJobDetailResponse = (
  body: JobDetailResponse | JobDetailPayload | TrainingJob | PipelineData,
): JobDetailPayload => {
  if (
    body &&
    typeof body === "object" &&
    "data" in body &&
    body.data &&
    typeof body.data === "object" &&
    !("_id" in body) &&
    !("read_dataset" in body) &&
    !("train" in body)
  ) {
    return body.data as JobDetailPayload;
  }
  return body as JobDetailPayload;
};

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

  // GET /api/v1/inference/jobs/{id} (returns PipelineData directly inside BaseResponse.data)
  getJobDetail: async (id: string): Promise<JobDetailPayload> => {
    const res = await client.get<JobDetailResponse | JobDetailPayload>(
      `/api/v1/inference/jobs/${id}`,
    );
    return unwrapJobDetailResponse(res.data);
  },

  // GET /api/v1/inference/jobs/{id}/pipeline
  getJobPipeline: async (id: string): Promise<PipelineData> => {
    const res = await client.get<JobDetailResponse | PipelineData>(
      `/api/v1/inference/jobs/${id}/pipeline`,
    );
    return unwrapJobDetailResponse(res.data) as PipelineData;
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

  getJobInfo: async (id: string): Promise<JobDetailPayload> => {
    const res = await client.get<JobDetailResponse | JobDetailPayload>(
      `/api/v1/inference/jobs/${id}`,
    );
    return unwrapJobDetailResponse(res.data);
  },

  getLegacyJobsByUserId: async (_userId?: string): Promise<TrainingJob[]> => {
    const res = await client.get<JobsListResponse>("/api/v1/inference/jobs", {
      params: { current_page: 1, page_size: 100, sort_time: "desc" },
    });
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
