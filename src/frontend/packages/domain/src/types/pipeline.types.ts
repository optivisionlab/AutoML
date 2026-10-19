export type PipelineNodeStatus = "pending" | "running" | "success" | "done" | "completed" | "failed" | "error" | null;

export interface PipelineBaseNode<TParams = Record<string, unknown>, TOutput = Record<string, unknown>> {
  name: string;
  kind: string;
  depends_on: string[];
  status: PipelineNodeStatus;
  started_at?: string | number | null;
  finished_at?: string | number | null;
  error?: string | null;
  params: TParams;
  output: TOutput;
}

export interface ReadDatasetParams {
  id_data?: string | null;
  format?: string | null;
  [key: string]: unknown;
}

export interface ReadDatasetOutput {
  data_url?: string | null;
  cache_hit?: boolean | null;
  [key: string]: unknown;
}

export interface SplitHoldoutParams {
  method?: string | null;
  test_size?: number | null;
  shuffle?: boolean | null;
  random_state?: number | null;
  [key: string]: unknown;
}

export interface SplitHoldoutOutput {
  train_rows?: number | null;
  holdout_rows?: number | null;
  [key: string]: unknown;
}

export interface ReadTrainingDataParams {
  split?: string | null;
  [key: string]: unknown;
}

export interface ReadTrainingDataOutput {
  n_rows?: number | null;
  n_columns?: number | null;
  [key: string]: unknown;
}

export interface PreprocessingParams {
  list_feature?: string[];
  target?: string | null;
  transformers?: {
    numeric?: string[];
    categorical?: string[];
    text?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface PreprocessingOutput {
  cache_hit?: boolean | null;
  dropped_rows?: number | null;
  column_types?: {
    numeric?: string[];
    categorical?: string[];
    text?: string[];
    [key: string]: unknown;
  } | null;
  [key: string]: unknown;
}


export interface ModelSelectionParams {
  problem_type?: string;
  model_names?: string[];
  search_algorithm?: string | null;
  max_time?: number | string | null;
  metric_sort?: string | null;
  metrics?: Record<string, string>;
  split?: {
    method?: string;
    n_splits?: number;
    shuffle?: boolean;
    random_state?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ModelScoreDetail {
  status: PipelineNodeStatus;
  error?: string | null;
  best_params?: Record<string, unknown> | null;
  scores?: Record<string, number> | null;
}

export interface TrainOutput {
  models?: Record<string, ModelScoreDetail>;
  [key: string]: unknown;
}

export interface SelectBestParams {
  dependency_policy?: string;
  [key: string]: unknown;
}

export interface SelectBestOutput {
  best_model?: string | null;
  time_limit_reached?: boolean | null;
  [key: string]: unknown;
}

export interface SaveResultParams {
  bucket_name?: string;
  [key: string]: unknown;
}

export interface SaveResultOutput {
  object_name?: string | null;
  [key: string]: unknown;
}

export interface PipelineData {
  job_id?: string | null;
  version?: string;
  mode?: string;
  status?: PipelineNodeStatus;
  updated_at?: string | number | null;
  read_dataset?: PipelineBaseNode<ReadDatasetParams, ReadDatasetOutput>;
  split_holdout_data?: PipelineBaseNode<SplitHoldoutParams, SplitHoldoutOutput>;
  read_training_data?: PipelineBaseNode<ReadTrainingDataParams, ReadTrainingDataOutput>;
  preprocessing?: PipelineBaseNode<PreprocessingParams, PreprocessingOutput>;
  model_selection?: PipelineBaseNode<ModelSelectionParams, Record<string, unknown>>;
  train?: PipelineBaseNode<Record<string, unknown>, TrainOutput>;
  select_best?: PipelineBaseNode<SelectBestParams, SelectBestOutput>;
  save_result?: PipelineBaseNode<SaveResultParams, SaveResultOutput>;
  [customNodeKey: string]: unknown;
}

export interface GetPipelineSamplePayload {
  problem_type: string;
  job_id?: string;
}

export interface PipelineSampleResponse {
  success: boolean;
  message: string;
  pipeline: PipelineData;
}
