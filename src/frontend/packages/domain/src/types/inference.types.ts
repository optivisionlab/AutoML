import { BaseResponse, PaginatedResponse, UniversalFile } from "./common.types";
import { TrainingJob } from "./job.types";

export interface PredictionFile {
  blob: Blob;
  fileName: string;
}

export interface InferencePayload {
  jobId: string;
  file: UniversalFile;
}

export interface ActivateModelPayload {
  jobId: string;
  activate: 0 | 1;
}

export interface FeatureSchemaItem {
  name: string;
  data_type: string;
  sample_value: unknown;
}

export interface CodeSnippets {
  curl: string;
  python: string;
  javascript: string;
  csharp: string;
  php: string;
}

export interface DeploymentInfoResponseData {
  job_id: string;
  model_name: string;
  status: "ACTIVE" | "INACTIVE" | string;
  activate: 0 | 1 | number;
  best_score: number;
  endpoint_url: string;
  features: string[];
  features_schema: FeatureSchemaItem[];
  sample_payload: {
    data: Array<Record<string, unknown>>;
  };
  code_snippets: CodeSnippets;
}

export type DeploymentInfoResponse = BaseResponse<DeploymentInfoResponseData>;

export interface RealtimePredictPayload {
  jobId: string;
  data: Array<Record<string, unknown>>;
}

export interface RealtimePredictResponseData {
  job_id: string;
  model_name: string;
  predictions: Array<number | string | boolean>;
  latency_ms: number;
  total_samples: number;
}

export type RealtimePredictResponse = BaseResponse<RealtimePredictResponseData>;

export interface BatchPredictFilePayload {
  jobId: string;
  file: UniversalFile;
}

export type ActiveModelsResponse = PaginatedResponse<TrainingJob>;
