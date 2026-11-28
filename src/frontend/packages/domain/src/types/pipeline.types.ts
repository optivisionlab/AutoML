export type PipelineNodeStatus =
  | "queued"
  | "pending"
  | "running"
  | "succeeded"
  | "done"
  | "success"
  | "completed"
  | "failed"
  | "error"
  | "skipped"
  | "cancelled"
  | null;

export type PipelineTrialStatus = PipelineNodeStatus | "pruned";

export interface PipelineError {
  message?: string;
  [key: string]: unknown;
}

export interface PipelineBaseNode<TParams = Record<string, unknown>, TOutput = Record<string, unknown>> {
  name: string;
  kind: string;
  depends_on: string[];
  status: PipelineNodeStatus;
  started_at?: string | number | null;
  finished_at?: string | number | null;
  error?: string | PipelineError | null;
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
  n_rows?: number | null;
  n_columns?: number | null;
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
  reason?: string | null;
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
  n_features?: number | null;
  column_types?: {
    numeric?: string[];
    categorical?: string[];
    text?: string[];
    [key: string]: unknown;
  } | null;
  class_distribution?: Record<string, number> | null;
  [key: string]: unknown;
}

export interface ModelSelectionParams {
  problem_type?: string | null;
  model_names?: string[];
  search_algorithm?: string | null;
  max_time?: number | string | null;
  timeout?: number | string | null;
  metric_sort?: string | null;
  metrics?: Record<string, string>;
  cv?: {
    name?: string | null;
    n_splits?: number | null;
    n_repeats?: number | null;
    description?: string | null;
    [key: string]: unknown;
  } | null;
  split?: {
    method?: string;
    n_splits?: number;
    shuffle?: boolean;
    random_state?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface ModelTrialDetail {
  trial_id?: number;
  number?: number;
  status?: PipelineTrialStatus | string;
  params?: Record<string, unknown> | null;
  scores?: Record<string, number | null> | null;
  cv_scores?: Record<string, number | null> | null;
  duration_sec?: number | null;
  started_at?: string | number | null;
  finished_at?: string | number | null;
  error?: string | null;
  [key: string]: unknown;
}

export type ModelTrial = ModelTrialDetail;

export interface ModelScoreDetail {
  status: PipelineNodeStatus;
  error?: string | PipelineError | null;
  started_at?: string | number | null;
  finished_at?: string | number | null;
  // Pipeline v2.0.0 schema fields
  trials?: ModelTrialDetail[] | null;
  best_trial?: number | null;
  best_scores?: Record<string, number | null> | null;
  holdout_scores?: Record<string, number | null> | null;
  n_trials?: number | null;
  n_pruned?: number | null;
  // Pipeline v1.0.0 backward-compatible fields
  best_params?: Record<string, unknown> | null;
  scores?: Record<string, number | null> | null;
  [key: string]: unknown;
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
  best_trial?: number | null;
  best_scores?: Record<string, number | null> | null;
  holdout_scores?: Record<string, number | null> | null;
  score_source?: "holdout" | "cv" | string | null;
  time_limit_reached?: boolean | null;
  [key: string]: unknown;
}

export interface SaveResultParams {
  bucket_name?: string;
  [key: string]: unknown;
}

export interface SaveResultOutput {
  object_name?: string | null;
  pipeline_object_name?: string | null;
  [key: string]: unknown;
}

export interface PipelineData {
  job_id?: string | null;
  version?: string;
  mode?: string;
  source?: "tracked" | "legacy" | string | null;
  status?: PipelineNodeStatus;
  error?: string | PipelineError | null;
  seq?: number;
  started_at?: string | number | null;
  finished_at?: string | number | null;
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

export interface PipelineNodeStartedEvent {
  event: "node_started";
  job_id: string;
  seq?: number;
  node: string;
  status: "running" | PipelineNodeStatus;
  at?: string;
}

export interface PipelineNodeFinishedEvent {
  event: "node_finished";
  job_id: string;
  seq?: number;
  node: string;
  status: PipelineNodeStatus;
  output?: Record<string, unknown> | null;
  error?: string | null;
  at?: string;
}

export interface PipelineModelFinishedEvent {
  event: "model_finished";
  job_id: string;
  seq?: number;
  node?: string;
  model_name: string;
  status: PipelineNodeStatus;
  best_trial?: number | null;
  best_scores?: Record<string, number | null> | null;
  best_params?: Record<string, unknown> | null;
  holdout_scores?: Record<string, number | null> | null;
  n_trials?: number | null;
  n_pruned?: number | null;
  error?: string | null;
  at?: string;
}

export interface PipelineJobFinishedEvent {
  event: "job_finished";
  job_id: string;
  seq?: number;
  status: PipelineNodeStatus;
  best_model?: string | null;
  holdout_scores?: Record<string, number | null> | null;
  error?: string | null;
  at?: string;
}

export interface PipelineSnapshotEvent {
  event: "snapshot";
  job_id: string;
  seq?: number;
  pipeline: PipelineData;
  at?: string;
}

export type PipelineRealtimeEvent =
  | PipelineNodeStartedEvent
  | PipelineNodeFinishedEvent
  | PipelineModelFinishedEvent
  | PipelineJobFinishedEvent
  | PipelineSnapshotEvent;

export interface GetPipelineSamplePayload {
  problem_type: string;
  job_id?: string;
}

export interface PipelineSampleResponse {
  success: boolean;
  message: string;
  pipeline: PipelineData;
}
