import { BaseResponse, PaginatedResponse } from "./common.types";
import { PipelineData } from "./pipeline.types";

export interface JobConfig {
  choose?: string;
  list_feature?: string[];
  metric_sort?: string;
  problem_type?: string;
  target?: string;
  search_algorithm?: string;
}

export interface OtherModelScore {
  model_id?: number | string;
  model?: string;
  model_name?: string;
  score?: number;
  scores?: Record<string, number | null>;
  best_params?: Record<string, unknown> | null;
}

export interface TrainingJob {
  _id: string;
  id?: string;
  job_id?: string;
  /** Legacy numeric: 0 = running/pending, 1 = succeeded, -1 = failed, -2 = cancelled. v2.0.0 string: queued | running | succeeded | failed | cancelled */
  status: number | string;
  activate?: number; // 0 = inactive, 1 = active/serving
  data?: {
    id?: string;
    name?: string;
  };
  user?: {
    id?: string;
    name?: string;
  };
  config?: JobConfig;
  best_model?: string;
  best_model_id?: number | string;
  best_score?: number;
  best_params?: Record<string, unknown> | null;
  holdout_scores?: Record<string, number | null> | null;
  orther_model_scores?: OtherModelScore[];
  create_at?: number;
  created_at?: number | string;
  updated_at?: number | string;
  finished_at?: number | string;
  infor?: string;
  error?: string | null;
  model?: unknown;
  pipeline?: PipelineData | null;
}

export interface JobsListParams {
  current_page?: number;
  page_size?: number;
  sort_name?: "asc" | "desc" | string | null;
  sort_time?: "asc" | "desc" | string | null;
}

export interface CancelJobResponseData {
  job_id: string;
  status: number | string; // -2 | "cancelled"
}

export type CancelJobResponse = BaseResponse<CancelJobResponseData>;

export type JobsListResponse = PaginatedResponse<TrainingJob>;
export type JobItemResponse = TrainingJob;
/**
 * Backend `GET /api/v1/inference/jobs/{id}` and `GET /api/v1/inference/jobs/{id}/pipeline`
 * return `BaseResponse<PipelineData>` directly in `data` (while legacy callers may also pass `TrainingJob`).
 */
export type JobDetailPayload = Partial<TrainingJob> & Partial<PipelineData>;
export type JobDetailResponse = BaseResponse<JobDetailPayload>;

export type GetJobsOffsetParams = {
  userId?: string;
  page?: number;
  limit?: number;
};
