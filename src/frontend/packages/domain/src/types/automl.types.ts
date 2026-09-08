export type FeatureMap = Record<string, boolean>;
export type MetricMap = Record<string, string>;

export type FeaturesResponse = {
  features: FeatureMap;
};

export type MetricsResponse = {
  metrics: MetricMap;
};

export type DataPreviewResponse = {
  rows: number;
  data: Record<string, unknown>[];
};

export type StartTrainingPayload = {
  choose?: string;
  problem_type?: string;
  target?: string;
  metric_sort?: string;
  features?: string[];
  [key: string]: unknown;
};

export type StartTrainingResponse = {
  status: string;
  message: string;
  job_id: string;
};
