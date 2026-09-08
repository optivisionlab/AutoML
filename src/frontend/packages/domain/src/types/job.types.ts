export type JobConfig = {
  choose?: string;
  list_feature?: string[];
  metric_sort?: string;
  problem_type?: string;
  target?: string;
};

export type OtherModelScore = {
  model_name: string;
  scores: Record<string, number>;
};

export type TrainingJob = {
  _id: string;
  job_id: string;
  data?: {
    name?: string;
  };
  config?: JobConfig;
  best_model?: string;
  best_model_id?: string;
  best_params?: unknown;
  best_score?: number;
  create_at?: number;
  model?: unknown;
  orther_model_scores?: OtherModelScore[];
  status: number | string;
};

export type GetJobsOffsetParams = {
  userId: string;
  page?: number;
  limit?: number;
};
