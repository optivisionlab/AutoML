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
  scores?: Record<string, number>;
  best_params?: Record<string, unknown> | null;
}

export interface TrainingJob {
  _id: string;
  job_id?: string;
  status: number | string; // 1 = completed, 0 = running/pending, -1 = failed, -2 = cancelled
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
  orther_model_scores?: OtherModelScore[];
  create_at?: number;
  infor?: string;
  model?: unknown;
  pipeline?: PipelineData;
}

export interface JobsListParams {
  current_page?: number;
  page_size?: number;
  sort_name?: "asc" | "desc" | string | null;
  sort_time?: "asc" | "desc" | string | null;
}

export interface CancelJobResponseData {
  job_id: string;
  status: number; // -2
}

export type CancelJobResponse = BaseResponse<CancelJobResponseData>;

export type JobsListResponse = PaginatedResponse<TrainingJob>;
export type JobItemResponse = TrainingJob;

export type GetJobsOffsetParams = {
  userId?: string;
  page?: number;
  limit?: number;
};
